"""
ai_feedback.py — Claude API integration (FR-026 to FR-031, Section 10).

Single responsibility: build a structured prompt from the analysis results,
send it to Claude, and return parsed recruiter-style feedback.

Designed to degrade gracefully (NFR-016, FR-031): if no API key is configured
or the API call fails, a deterministic rule-based fallback is returned so the
rest of the app keeps working. The response shape is identical either way.
"""

import json
import os

MODEL = "claude-sonnet-5"  # current model id (SRS predated this)
MAX_TOKENS = 1500
TIMEOUT_SECONDS = 30

# Anthropic client is optional at import time.
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None


def generate_feedback(resume_text: str, jd_text: str, analysis: dict) -> dict:
    """Generate recruiter-style feedback for the resume.

    Args:
        resume_text: Raw (uncleaned) resume text — Claude reads better prose.
        jd_text: The job description as provided by the user.
        analysis: The dict returned by ats_scorer.score().

    Returns:
        Dict with keys: strengths, weaknesses, improved_summary,
        rewrite_suggestions, skill_gap_roadmap, and a meta field
        'source' = 'claude' | 'fallback'.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key or Anthropic is None:
        return _fallback(analysis, reason="no_api_key")

    try:
        client = Anthropic(api_key=api_key, timeout=TIMEOUT_SECONDS)
        prompt = _build_prompt(resume_text, jd_text, analysis)
        message = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text
        data = _parse_json(text)
        data["source"] = "claude"
        return data
    except Exception as exc:  # noqa: BLE001 — any failure must not break the app
        fb = _fallback(analysis, reason="api_error")
        fb["error_detail"] = str(exc)[:200]
        return fb


def _build_prompt(resume_text: str, jd_text: str, analysis: dict) -> str:
    """Construct the structured prompt (Section 10.1)."""
    return f"""You are an experienced technical recruiter and ATS specialist.
Analyze the following resume against the job description and respond with
practical, specific, encouraging feedback.

ATS SCORE: {analysis['ats_score']} / 100 (Grade {analysis['grade']} — {analysis['level']})
MATCHED KEYWORDS: {', '.join(analysis['matched_keywords']) or 'none'}
MISSING KEYWORDS: {', '.join(analysis['missing_keywords']) or 'none'}
SECTIONS PRESENT: {', '.join(analysis['sections_found']) or 'none'}

--- JOB DESCRIPTION ---
{jd_text[:4000]}

--- RESUME ---
{resume_text[:6000]}

Respond ONLY with valid JSON (no markdown fences) in exactly this shape:
{{
  "strengths": ["3-5 short specific strengths"],
  "weaknesses": ["3-5 short specific weaknesses"],
  "improved_summary": "a rewritten 3-4 sentence professional summary",
  "rewrite_suggestions": ["3-5 improved, quantified bullet points"],
  "skill_gap_roadmap": [
    {{"skill": "missing skill", "why": "why it matters", "resource": "how to learn it"}}
  ]
}}"""


def _parse_json(text: str) -> dict:
    """Extract the JSON object from Claude's response, tolerating stray text."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    return json.loads(text)


def _fallback(analysis: dict, reason: str) -> dict:
    """Deterministic feedback when Claude is unavailable (FR-031, NFR-016)."""
    missing = analysis.get("missing_keywords", [])
    matched = analysis.get("matched_keywords", [])
    sections_missing = analysis.get("sections_missing", [])

    strengths = []
    if matched:
        strengths.append(
            f"Your resume already matches {len(matched)} key terms from the "
            f"job description, including: {', '.join(matched[:6])}."
        )
    if analysis.get("sections_found"):
        strengths.append(
            "Core sections are present: "
            f"{', '.join(analysis['sections_found'])}."
        )
    strengths.append(
        f"Overall ATS match is {analysis['ats_score']}/100 "
        f"(Grade {analysis['grade']})."
    )

    weaknesses = []
    if missing:
        weaknesses.append(
            f"{len(missing)} job-description keywords are missing, e.g.: "
            f"{', '.join(missing[:6])}."
        )
    if sections_missing:
        weaknesses.append(
            "Consider adding these standard sections: "
            f"{', '.join(sections_missing)}."
        )
    if analysis["breakdown"]["tfidf"] < 40:
        weaknesses.append(
            "Overall wording overlap with the job description is low — mirror "
            "the language used in the posting where it's honestly true of you."
        )

    roadmap = [
        {
            "skill": kw,
            "why": "Appears in the job description but not in your resume.",
            "resource": "Add it if you have the experience, or take a short "
                        "online course (Coursera / freeCodeCamp / official docs).",
        }
        for kw in missing[:5]
    ]

    note = (
        "AI feedback is running in offline mode (no ANTHROPIC_API_KEY set). "
        "The analysis above is rule-based. Add an API key to get "
        "Claude-generated recruiter feedback."
        if reason == "no_api_key"
        else "AI feedback is temporarily unavailable; showing rule-based "
             "results instead."
    )

    return {
        "strengths": strengths,
        "weaknesses": weaknesses,
        "improved_summary": note,
        "rewrite_suggestions": [
            "Start each bullet with a strong action verb (built, led, "
            "improved).",
            "Quantify impact where possible (e.g. 'reduced load time by 40%').",
            "Tailor the summary to include the top missing keywords above.",
        ],
        "skill_gap_roadmap": roadmap,
        "source": "fallback",
        "notice": note,
    }
