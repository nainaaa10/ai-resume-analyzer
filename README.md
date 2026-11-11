# AI Resume Analyzer

An intelligent resume evaluation platform that mimics real Applicant Tracking
System (ATS) behavior. Upload a resume, paste a job description, and get an
ATS match score, keyword gap analysis, and recruiter-style feedback.

Built to spec from a formal IEEE-830 style Software Requirements Specification.

## How it works

```
Upload → text extraction → NLP pipeline → TF-IDF ATS scoring → Claude feedback → dashboard
```

| Layer | Tech |
|-------|------|
| Backend | Python 3.11+, Flask |
| Parsing | pdfplumber (PDF), python-docx (DOCX) |
| NLP | spaCy (`en_core_web_sm`) |
| ATS scoring | scikit-learn (TF-IDF + cosine similarity) |
| AI feedback | Anthropic Claude API |
| Frontend | Vanilla HTML/CSS/JS dashboard |

**Scoring weights:** TF-IDF cosine similarity 50% · keyword match 30% · section completeness 20%.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r backend/requirements.txt
python -m spacy download en_core_web_sm
```

### Add your Claude API key (optional)

```bash
cp .env.example .env
# then edit .env and set ANTHROPIC_API_KEY=...
```

Without a key the app runs in **offline mode**: everything works except the
AI feedback, which falls back to rule-based suggestions. Add a key to get
Claude-generated recruiter feedback.

## Run

```bash
cd backend
python app.py
```

Open http://localhost:5000 (set `PORT` to change).

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serves the dashboard |
| `/analyze` | POST | `resume` (file) + `job_description` (form field) → JSON results |
| `/health` | GET | `{status, spacy_model, claude_configured}` |

## Project structure

```
backend/
  app.py            Flask API + orchestration
  parser.py         PDF/DOCX text extraction
  nlp_processor.py  spaCy NLP pipeline + skill/section detection
  ats_scorer.py     TF-IDF cosine similarity scoring
  ai_feedback.py    Claude integration (with graceful fallback)
  requirements.txt
frontend/
  index.html · style.css · script.js
sample_data/        Test resume(s)
.env.example
```

## Notes

- Files are processed in-memory only — nothing is written to disk (NFR-007).
- The Claude API key stays server-side in `.env` and is never sent to the
  browser (NFR-006).
- Image-based/scanned PDFs are not supported (text-based PDFs only).
