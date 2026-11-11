"""
app.py — Flask REST API (Section 5.4).

Orchestrates the pipeline: parser -> nlp_processor -> ats_scorer ->
ai_feedback, and serves the frontend.

Endpoints:
    GET  /         -> renders the frontend
    POST /analyze  -> runs the full analysis, returns JSON
    GET  /health   -> health check for deployment
"""

import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

import ai_feedback
import ats_scorer
import nlp_processor
from parser import ExtractionError, extract_text

load_dotenv()

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB (FR-003)
ALLOWED_EXTENSIONS = (".pdf", ".docx")  # (FR-001, FR-002, FR-004)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_BYTES


@app.route("/")
def index():
    """Serve the single-page frontend."""
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/health")
def health():
    """Deployment health check."""
    return jsonify(
        {
            "status": "ok",
            "spacy_model": nlp_processor.SPACY_AVAILABLE,
            "claude_configured": bool(os.getenv("ANTHROPIC_API_KEY")),
        }
    )


@app.route("/analyze", methods=["POST"])
def analyze():
    """Run the full resume analysis pipeline (UC-001)."""
    # --- Validate inputs -----------------------------------------------
    if "resume" not in request.files:
        return _error("No resume file was uploaded.", 400)

    file = request.files["resume"]
    if not file.filename:
        return _error("No resume file was selected.", 400)

    if not file.filename.lower().endswith(ALLOWED_EXTENSIONS):
        return _error(
            "Unsupported file type. Please upload a PDF or DOCX file.", 400
        )

    job_description = (request.form.get("job_description") or "").strip()
    if not job_description:
        return _error("Please paste a job description to compare against.", 400)

    file_bytes = file.read()
    if len(file_bytes) > MAX_FILE_BYTES:
        return _error("File is too large. Maximum size is 5 MB.", 400)

    # --- Pipeline ------------------------------------------------------
    try:
        resume_text = extract_text(file.filename, file_bytes)
    except ExtractionError as exc:
        return _error(str(exc), 422)

    resume_nlp = nlp_processor.process(resume_text)
    jd_nlp = nlp_processor.process(job_description)

    analysis = ats_scorer.score(
        resume_nlp["cleaned_text"],
        jd_nlp["cleaned_text"],
        resume_nlp["sections_found"],
    )

    feedback = ai_feedback.generate_feedback(resume_text, job_description, analysis)

    return jsonify(
        {
            "ats_score": analysis["ats_score"],
            "grade": analysis["grade"],
            "level": analysis["level"],
            "recommendation": analysis["recommendation"],
            "breakdown": analysis["breakdown"],
            "matched_keywords": analysis["matched_keywords"],
            "missing_keywords": analysis["missing_keywords"],
            "sections_found": analysis["sections_found"],
            "sections_missing": analysis["sections_missing"],
            "resume_skills": resume_nlp["skills"],
            "jd_skills": jd_nlp["skills"],
            "entities": resume_nlp["entities"],
            "action_verbs_used": resume_nlp["action_verbs_used"],
            "ai_feedback": feedback,
        }
    )


@app.errorhandler(413)
def too_large(_e):
    """Triggered when MAX_CONTENT_LENGTH is exceeded (FR-003)."""
    return _error("File is too large. Maximum size is 5 MB.", 413)


def _error(message: str, status: int):
    """Uniform JSON error response with a plain-English message (NFR-011)."""
    return jsonify({"error": message}), status


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"  # NFR-009
    app.run(host="0.0.0.0", port=port, debug=debug)
