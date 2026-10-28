# ResearchMind — Intelligent Research Discovery and Knowledge Graph System

Live: https://researchmind-eight.vercel.app (Vercel project `researchmind`, Hobby, shvm51)
Repo: https://github.com/shvm51/researchmind
Dashboard: https://vercel.com/shvm51/researchmind

Upload research PDFs, inspect a typed knowledge graph, ask questions with
page-level citations, and explore explainable, collection-only research
opportunities. No fake statistics: every dashboard number comes from SQLite.

> Vercel demo note: the live deployment stores data in `/tmp` (see `vercel.json`),
> so uploaded papers are ephemeral — they may disappear when the serverless
> instance recycles. For persistent use, run the backend locally or on a
> persistent host (below) and point the frontend at it.
>
> Upload size note: Vercel serverless functions reject single requests over
> ~4.5 MB, so the frontend automatically splits files over 4 MB into 3 MB
> chunks (`/api/documents/upload-chunk` + `/api/documents/upload-complete`).
> The 50 MB backend cap still applies to the reassembled file.

## Quick start (10 min)

Backend:
```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # optional; defaults work with no LLM
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
# API docs: http://127.0.0.1:8000/docs  |  Health: /health
```
Frontend:
```bash
cd frontend
npm install && npm run dev   # http://localhost:5173 (proxies /api to :8000)
```

## Run tests
```bash
cd backend && .venv/bin/python -m pytest tests -q
```
Verified 2026-10-28: 3 tests pass — upload → graph → ask → gaps →
recommendations, duplicate detection, delete cascade, gap-score renormalisation.

## Reset / rebuild indexes
```bash
rm -rf backend/data researchmind.db   # or set RESEARCHMIND_DATA_DIR
# then re-upload PDFs, or POST /api/documents/{id}/reprocess per paper
```

## Architecture
See `ARCHITECTURE.md`. Flow: PDF (PyMuPDF) → page-preserving chunks →
heuristic NLP (spaCy optional) → SQLite entities/relationships → TF-IDF
embeddings (sentence-transformers optional) → hybrid retrieval → Cytoscape
graph → gap scoring → K-Means topics → recommendations.

## LLM configuration (optional)
Default provider is `none`: answers are extractive syntheses from cited
evidence and are labelled `extractive_fallback`. Set in `.env`:
`RESEARCHMIND_LLM_PROVIDER=openai`, `RESEARCHMIND_LLM_MODEL`,
`RESEARCHMIND_LLM_API_KEY`. Only short evidence snippets are sent, never
full documents, and any provider error falls back to the extractive answer.
Never hardcode credentials; see `backend/.env.example` (no secrets in it).

## Known limitations
- Entity/relation extraction is heuristic (lexicon + patterns), not a
  trained NER model — audit every edge via its snippet before citing it.
- Embeddings default to TF-IDF; semantic quality improves only if
  sentence-transformers is installed and configured.
- Gap scores are tunable heuristics, not probabilities, and are valid
  only for the uploaded collection — never a verified global gap.
- Scanned PDFs are flagged as failed; OCR is not implemented (optional extension).
- Graph view truncates at 500 nodes / 1000 edges; use filters and search.

## Project layout
```
researchmind/
  backend/app/{main,config,db}.py
  backend/app/services/{pdf_extract,chunking,nlp,embeddings,retrieval,llm,gaps,topics,recommendations}.py
  backend/tests/test_researchmind.py   # synthetic, clearly labelled fixtures
  frontend/src/{App,main}.tsx          # dashboard, library, graph, assistant, gaps, topics
  ARCHITECTURE.md  docs/{API,EVALUATION,INTELLIGENT_SYSTEMS}.md
```
