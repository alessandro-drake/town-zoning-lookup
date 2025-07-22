# analysis_api.py  -----------------------------------------------------------------
"""
Background-analysis micro-service.
──────────────────────────────────
Responsibilities
1. Accept a PDF link (found by ordinance_finder) & enqueue a heavy analysis job.
2. Expose:
   • POST  /api/analyze   -> returns {"job_id": …}
   • GET   /api/status/<job_id> -> {"state": PENDING|SUCCESS|FAILURE, "result": …}
3. Celery worker executes utils.pdf_parser.analyze_pdf and stores the output.
"""

import os, json
from flask import Blueprint, request, jsonify
from dotenv import load_dotenv
from celery import Celery
from anthropic import Anthropic                # LLM client shared by workers
from utils import pdf_parser                   # your helper module

# --------------------------------------------------------------------------- config
load_dotenv()

BROKER_URL   = os.getenv("REDIS_URL", "redis://localhost:6379/0")
RESULT_BACK  = os.getenv("REDIS_URL", "redis://localhost:6379/0")

anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

celery_app = Celery("analysis",
                    broker=BROKER_URL,
                    backend=RESULT_BACK)

# Limit worker RAM if you like:
# celery_app.conf.worker_max_tasks_per_child = 20

# ------------------------------------------------------------------ Celery task
@celery_app.task(bind=True, name="analyze_pdf_task")
def analyze_pdf_task(self, pdf_url: str) -> dict:
    """
    Heavy-lifting task → returns {summary: str, scores: {...}}.
    """
    # Load scoring config once per worker
    best_prac  = _lazy_json("config/best_practices.json")
    weights    = _lazy_json("config/scoring_weights.json")

    return pdf_parser.analyze_pdf(
        url            = pdf_url,
        client         = anthropic_client,
        best_practices = best_prac,
        weights        = weights,
    )


# --------------------------- helper to lazily read / cache json files
_json_cache = {}
def _lazy_json(path: str):
    if path not in _json_cache:
        with open(path, "r", encoding="utf-8") as f:
            _json_cache[path] = json.load(f)
    return _json_cache[path]


# ------------------------------------------------------------------ Flask blueprint
bp = Blueprint("analysis_api", __name__)

@bp.route("/api/analyze", methods=["POST"])
def api_analyze():
    """
    Kick off a background job. Expects {"link": "<pdf url>"}.
    """
    data = request.get_json(silent=True) or {}
    pdf_link = (data.get("link") or "").strip()
    if not pdf_link:
        return jsonify({"error": "Missing 'link'"}), 400

    job = analyze_pdf_task.apply_async(args=[pdf_link])
    return jsonify({"job_id": job.id})

@bp.route("/api/status/<job_id>", methods=["GET"])
def api_status(job_id: str):
    """
    Poll job status. SUCCESS returns the final payload.
    """
    async_result = celery_app.AsyncResult(job_id)
    if async_result.state == "PENDING":
        resp = {"state": "PENDING"}
    elif async_result.state == "FAILURE":
        resp = {"state": "FAILURE", "error": str(async_result.result)}
    elif async_result.state == "SUCCESS":
        resp = {"state": "SUCCESS", "result": async_result.result}
    else:  # RETRY, STARTED etc.
        resp = {"state": async_result.state}

    return jsonify(resp)

# ---------------------------- factory method so main.py can register blueprint
def register_to(app):
    app.register_blueprint(bp)
