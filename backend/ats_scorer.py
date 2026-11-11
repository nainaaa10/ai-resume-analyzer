"""
ats_scorer.py — ATS scoring engine (FR-018 to FR-025, Section 9).

Single responsibility: given cleaned resume and JD text plus section info,
compute a weighted ATS score and its component breakdown.

Weighting (FR-024 / Section 9.1):
    TF-IDF cosine similarity  50%
    Keyword match rate        30%
    Section completeness      20%
"""

import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from nlp_processor import STANDARD_SECTIONS

WEIGHTS = {"tfidf": 0.50, "keywords": 0.30, "sections": 0.20}

# JD keywords shorter than this are ignored for gap analysis (noise reduction).
_MIN_KEYWORD_LEN = 3


def score(resume_cleaned: str, jd_cleaned: str, sections_found: list) -> dict:
    """Compute the full ATS score and breakdown.

    Args:
        resume_cleaned: Cleaned resume text (from nlp_processor).
        jd_cleaned: Cleaned job-description text.
        sections_found: List of standard sections present in the resume.

    Returns:
        Dict with the final score, letter grade, component scores, and
        matched/missing keyword lists.
    """
    tfidf_score = _tfidf_similarity(resume_cleaned, jd_cleaned)
    matched, missing = _keyword_gap(resume_cleaned, jd_cleaned)

    total_jd_kw = len(matched) + len(missing)
    keyword_score = (len(matched) / total_jd_kw * 100) if total_jd_kw else 0.0

    section_score = len(sections_found) / len(STANDARD_SECTIONS) * 100

    final = (
        tfidf_score * WEIGHTS["tfidf"]
        + keyword_score * WEIGHTS["keywords"]
        + section_score * WEIGHTS["sections"]
    )
    final = round(final, 1)

    grade, level, recommendation = _grade(final)

    return {
        "ats_score": final,
        "grade": grade,
        "level": level,
        "recommendation": recommendation,
        "breakdown": {
            "tfidf": round(tfidf_score, 1),
            "keywords": round(keyword_score, 1),
            "sections": round(section_score, 1),
        },
        "matched_keywords": matched,
        "missing_keywords": missing,
        "sections_found": sections_found,
        "sections_missing": [s for s in STANDARD_SECTIONS if s not in sections_found],
    }


def _tfidf_similarity(resume: str, jd: str) -> float:
    """TF-IDF + cosine similarity, normalized to 0–100 (FR-018, FR-019)."""
    if not resume.strip() or not jd.strip():
        return 0.0

    vectorizer = TfidfVectorizer(
        stop_words="english", ngram_range=(1, 2), max_features=5000
    )
    try:
        matrix = vectorizer.fit_transform([resume, jd])
    except ValueError:
        # Happens if vocabulary is empty after stopword removal.
        return 0.0

    similarity = cosine_similarity(matrix[0:1], matrix[1:2])[0][0]
    return float(similarity) * 100


def _keyword_gap(resume: str, jd: str) -> tuple:
    """Identify JD keywords matched vs missing in resume (FR-020, FR-021)."""
    resume_tokens = set(re.findall(r"[a-z0-9+#.]{2,}", resume))
    jd_tokens = [t for t in re.findall(r"[a-z0-9+#.]+", jd)
                 if len(t) >= _MIN_KEYWORD_LEN]

    matched, missing = [], []
    for token in dict.fromkeys(jd_tokens):  # de-dupe, preserve order
        (matched if token in resume_tokens else missing).append(token)

    # Cap lists so the UI stays readable.
    return matched[:40], missing[:40]


def _grade(score_value: float) -> tuple:
    """Map a 0–100 score to (grade, level, recommendation) — Section 9.2."""
    if score_value >= 80:
        return "A", "Excellent", "Strong match — submit with confidence."
    if score_value >= 65:
        return "B", "Good", "Minor optimizations recommended."
    if score_value >= 50:
        return "C", "Average", "Add missing keywords, strengthen sections."
    if score_value >= 35:
        return "D", "Below Average", "Significant tailoring required."
    return "F", "Poor", "Resume needs major restructuring for this role."
