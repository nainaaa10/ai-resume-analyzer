"""
parser.py — Resume file parsing (FR-007 to FR-010).

Single responsibility: given an uploaded file (in-memory bytes), detect its
type and extract raw, human-readable text. No disk writes — everything is
processed from in-memory byte streams (NFR-007).
"""

import io

import pdfplumber
from docx import Document


class ExtractionError(Exception):
    """Raised when text cannot be meaningfully extracted from a file."""


def extract_text(filename: str, file_bytes: bytes) -> str:
    """Extract text from an uploaded resume file.

    Args:
        filename: Original filename, used only to detect the extension.
        file_bytes: Raw bytes of the uploaded file.

    Returns:
        Cleaned, whitespace-normalized text extracted from the document.

    Raises:
        ExtractionError: If the format is unsupported, or if extraction
            yields empty content (e.g. an image-based/scanned PDF).
    """
    name = (filename or "").lower()

    if name.endswith(".pdf"):
        text = _extract_pdf(file_bytes)
    elif name.endswith(".docx"):
        text = _extract_docx(file_bytes)
    else:
        raise ExtractionError(
            "Unsupported file format. Please upload a text-based PDF or DOCX file."
        )

    text = _normalize(text)

    if not text.strip():
        raise ExtractionError(
            "No readable text found. If this is a scanned or image-based PDF, "
            "please upload a text-based version instead."
        )

    return text


def _extract_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF, preserving logical reading order (FR-010)."""
    parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text:
                parts.append(page_text)
    return "\n".join(parts)


def _extract_docx(file_bytes: bytes) -> str:
    """Extract paragraph and table text from a DOCX file (FR-008)."""
    document = Document(io.BytesIO(file_bytes))
    parts = [p.text for p in document.paragraphs if p.text.strip()]

    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))

    return "\n".join(parts)


def _normalize(text: str) -> str:
    """Collapse excessive whitespace while keeping line structure."""
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)
