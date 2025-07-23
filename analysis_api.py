# analysis_api.py  -----------------------------------------------------------------
"""
Synchronous analysis micro-service (no Celery).
─────────────────────────────────────────────
Responsibilities
1. Accept a PDF link (found by ordinance_finder) & run analysis immediately.
2. Expose:
   • POST  /api/analyze       -> returns {"job_id": …} (202 Accepted)
   • GET   /api/status/<job_id> -> {"state": PENDING|SUCCESS|FAILURE, "result"/"error": …}
"""

import os
import json
import uuid
from flask import Blueprint, request, jsonify
from dotenv import load_dotenv
from anthropic import Anthropic                # LLM client shared by workers
from utils import pdf_parser                   # your helper module

# --------------------------------------------------------------------------- config
load_dotenv()
anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ------------------------------------------------------------------ JSON helper
_json_cache = {}
def _lazy_json(path: str):
    if path not in _json_cache:
        with open(path, "r", encoding="utf-8") as f:
            _json_cache[path] = json.load(f)
    return _json_cache[path]

# --------------------------------------------------------- in-memory job store
JOBS: dict[str, dict] = {}

# ------------------------------------------------------------------ Flask blueprint
bp = Blueprint("analysis_api", __name__)

@bp.route("/api/analyze", methods=["POST"])
def api_analyze():
    """
    Kick off a (synchronous) analysis job. Expects {"link": "<pdf url>"}.
    Returns 202 with a job_id you can poll.
    """
    data     = request.get_json(silent=True) or {}
    pdf_link = (data.get("link") or "").strip()
    if not pdf_link:
        return jsonify({"error": "Missing 'link'"}), 400

    job_id = uuid.uuid4().hex
    JOBS[job_id] = {"state": "PENDING"}

    try:
        # load configs once per request
        best_prac = _lazy_json("config/best_practices.json")
        weights   = _lazy_json("config/scoring_weights.json")

        result = pdf_parser.analyze_pdf(
            url            = pdf_link,
            client         = anthropic_client,
            best_practices = best_prac,
            weights        = weights,
        )

        JOBS[job_id] = {"state": "SUCCESS", "result": result}
    except Exception as e:
        JOBS[job_id] = {"state": "FAILURE", "error": str(e)}

    return jsonify({"job_id": job_id}), 202

@bp.route("/api/status/<job_id>", methods=["GET"])
def api_status(job_id: str):
    """
    Poll job status. 
    • PENDING until the POST handler completes.
    • SUCCESS returns {"state":"SUCCESS","result":…}
    • FAILURE returns {"state":"FAILURE","error":…}
    """
    job = JOBS.get(job_id)
    if job is None:
        return jsonify({"error": "Unknown job_id"}), 404
    return jsonify(job)

def register_to(app):
    app.register_blueprint(bp)
