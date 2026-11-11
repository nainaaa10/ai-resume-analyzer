"""
nlp_processor.py — NLP preprocessing pipeline (FR-011 to FR-017).

Single responsibility: turn raw resume text into a structured dictionary of
cleaned text, detected skills, named entities, and keywords.

spaCy is used when available for lemmatization, stopword removal, and entity
recognition. If the spaCy model isn't installed, the module degrades
gracefully to a regex/stopword-list pipeline so the app still runs (NFR-016
spirit: core features work without optional heavy dependencies).
"""

import re

# ---------------------------------------------------------------------------
# Skill database (FR-016). Defined as a standalone constant for easy
# extension (NFR-019). 60+ technologies across common domains.
# ---------------------------------------------------------------------------
SKILL_DATABASE = [
    # Languages
    "python", "java", "javascript", "typescript", "c++", "c#", "c", "go",
    "rust", "ruby", "php", "swift", "kotlin", "scala", "r", "matlab", "sql",
    # Web / frontend
    "html", "css", "react", "angular", "vue", "next.js", "node.js", "express",
    "django", "flask", "fastapi", "spring", "spring boot", "rest api", "graphql",
    # Data / ML
    "machine learning", "deep learning", "nlp", "computer vision",
    "tensorflow", "pytorch", "keras", "scikit-learn", "pandas", "numpy",
    "data analysis", "data science", "tableau", "power bi", "spark", "hadoop",
    # Databases
    "mysql", "postgresql", "mongodb", "redis", "sqlite", "oracle", "cassandra",
    "elasticsearch", "dynamodb",
    # Cloud / DevOps
    "aws", "azure", "gcp", "docker", "kubernetes", "jenkins", "terraform",
    "ci/cd", "git", "github", "gitlab", "linux", "bash",
    # Concepts
    "agile", "scrum", "microservices", "oop", "data structures", "algorithms",
    "system design", "api design", "unit testing", "tdd",
]

# 8 standard resume sections (FR-022).
STANDARD_SECTIONS = [
    "summary", "experience", "education", "skills",
    "projects", "certifications", "achievements", "contact",
]

# 20 curated action verbs (FR-023).
ACTION_VERBS = [
    "built", "designed", "developed", "implemented", "created", "led",
    "managed", "improved", "increased", "reduced", "optimized", "launched",
    "delivered", "achieved", "engineered", "automated", "architected",
    "streamlined", "spearheaded", "collaborated",
]

# Minimal English stopword set for the fallback path (when spaCy is absent).
_FALLBACK_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "are", "was", "were", "be",
    "been", "being", "this", "that", "these", "those", "it", "its", "i",
    "we", "you", "he", "she", "they", "them", "my", "our", "your", "their",
}

# Try to load spaCy once at import time; cache the model in memory.
try:
    import spacy

    try:
        _NLP = spacy.load("en_core_web_sm")
    except OSError:
        _NLP = None  # model not downloaded
except ImportError:
    spacy = None
    _NLP = None

SPACY_AVAILABLE = _NLP is not None


def process(text: str) -> dict:
    """Run the full NLP pipeline over resume (or JD) text.

    Args:
        text: Raw extracted text.

    Returns:
        Dict with keys: cleaned_text, skills, entities, keywords,
        sections_found, action_verbs_used.
    """
    raw_lower = text.lower()

    stripped = _strip_pii(raw_lower)
    cleaned = _clean(stripped)

    return {
        "cleaned_text": cleaned,
        "skills": detect_skills(raw_lower),
        "entities": _extract_entities(text),
        "keywords": _keywords(cleaned),
        "sections_found": detect_sections(raw_lower),
        "action_verbs_used": _detect_action_verbs(raw_lower),
    }


def _strip_pii(text: str) -> str:
    """Remove emails, URLs, and phone numbers (FR-012)."""
    text = re.sub(r"\S+@\S+", " ", text)
    text = re.sub(r"http\S+|www\.\S+", " ", text)
    text = re.sub(r"\+?\d[\d\-\s().]{7,}\d", " ", text)
    return text


def _clean(text: str) -> str:
    """Lowercase, remove stopwords, lemmatize (FR-011, FR-013, FR-014)."""
    if _NLP is not None:
        doc = _NLP(text)
        tokens = [
            tok.lemma_
            for tok in doc
            if not tok.is_stop and not tok.is_punct and not tok.is_space
            and tok.lemma_.strip()
        ]
        return " ".join(tokens)

    # Fallback: regex tokenize + stopword removal (no lemmatization).
    tokens = re.findall(r"[a-z0-9+#.]+", text)
    tokens = [t for t in tokens if t not in _FALLBACK_STOPWORDS and len(t) > 1]
    return " ".join(tokens)


def _extract_entities(text: str) -> dict:
    """Extract named entities: orgs, dates, locations, persons (FR-015)."""
    result = {"organizations": [], "dates": [], "locations": [], "persons": []}
    if _NLP is None:
        return result

    doc = _NLP(text)
    label_map = {
        "ORG": "organizations",
        "DATE": "dates",
        "GPE": "locations",
        "LOC": "locations",
        "PERSON": "persons",
    }
    for ent in doc.ents:
        key = label_map.get(ent.label_)
        if key and ent.text.strip() not in result[key]:
            result[key].append(ent.text.strip())

    # Keep entity lists reasonable in size.
    for key in result:
        result[key] = result[key][:15]
    return result


def detect_skills(text_lower: str) -> list:
    """Detect skills from SKILL_DATABASE present in the text (FR-016)."""
    found = []
    for skill in SKILL_DATABASE:
        # Word-boundary match; escape regex metachars in skills like c++.
        pattern = r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])"
        if re.search(pattern, text_lower):
            found.append(skill)
    return found


def detect_sections(text_lower: str) -> list:
    """Return which of the 8 standard sections appear in the text (FR-022)."""
    found = []
    for section in STANDARD_SECTIONS:
        if re.search(r"(?<![a-z])" + re.escape(section) + r"(?![a-z])", text_lower):
            found.append(section)
    return found


def _detect_action_verbs(text_lower: str) -> list:
    """Return action verbs from the curated list found in text (FR-023)."""
    return [v for v in ACTION_VERBS
            if re.search(r"(?<![a-z])" + v + r"(?![a-z])", text_lower)]


def _keywords(cleaned_text: str) -> list:
    """Return the set of distinct meaningful tokens (for gap analysis)."""
    tokens = re.findall(r"[a-z0-9+#.]{2,}", cleaned_text)
    seen = []
    for t in tokens:
        if t not in seen:
            seen.append(t)
    return seen
