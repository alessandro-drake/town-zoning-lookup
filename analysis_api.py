# analysis_api.py  -----------------------------------------------------------------
"""
Synchronous analysis micro-service.
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
from anthropic import Anthropic
from utils import pdf_parser

load_dotenv()
anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

_json_cache = {}
def _lazy_json(path: str):
    if path not in _json_cache:
        with open(path, "r", encoding="utf-8") as f:
            _json_cache[path] = json.load(f)
    return _json_cache[path]

JOBS: dict[str, dict] = {}
bp = Blueprint("analysis_api", __name__)

@bp.route("/api/analyze", methods=["POST"])
def api_analyze():
    """Kicks off a synchronous analysis job."""
    print("\n--- /api/analyze endpoint hit! ---")
    data = request.get_json(silent=True) or {}
    pdf_link = (data.get("link") or "").strip()
    print(f"Received link: {pdf_link if pdf_link else 'None'}")
    if not pdf_link:
        return jsonify({"error": "Missing 'link'"}), 400

    job_id = uuid.uuid4().hex
    JOBS[job_id] = {"state": "PENDING"}
    print(f"Created job_id: {job_id}")

    try:
        # <-- KEY CHANGE: Only one config file is needed now.
        best_prac_data = _lazy_json("config/best_practices.json")
        print("Starting PDF analysis...")
        # The line for loading weights.json is removed.

        result = pdf_parser.analyze_pdf(
            url=pdf_link,
            client=anthropic_client,
            best_practices_data=best_prac_data, # Pass the single data object
        )

        print("Analysis successful.")
        JOBS[job_id] = {"state": "SUCCESS", "result": result}
    except Exception as e:
        print(f"!!! ANALYSIS FAILED: {e}")
        JOBS[job_id] = {"state": "FAILURE", "error": str(e)}

    return jsonify({"job_id": job_id}), 202

@bp.route("/api/status/<job_id>", methods=["GET"])
def api_status(job_id: str):
    """Polls job status."""
    job = JOBS.get(job_id)
    if job is None:
        return jsonify({"error": "Unknown job_id"}), 404
    return jsonify(job)

def register_to(app):
    app.register_blueprint(bp)