# Architecture

## Data flow
1. Upload (FastAPI, multipart, PDF-only, 50 MB cap, SHA-256 dedup) → stored under `data/uploads/`.
2. PyMuPDF extracts text per page. If ≥80% of pages yield <20 chars, the paper is marked `failed` with a scanned-PDF message; no fake text is invented.
3. Sentence-aware chunking (~900 chars) preserves `doc_id`, `page`, `offset_chars`.
4. Heuristic NLP (`services/nlp.py`) extracts typed entities and paper-level + co-occurrence relationships. Deduplication is exact on the normalized name only — similar names are never merged.
5. All rows persist in SQLite (`documents`, `chunks`, `entities`, `relationships`, `questions`, `gap_feedback`). Deleting a document cascades (foreign keys + file removal).
6. Retrieval: TF-IDF cosine (or sentence-transformers if configured) + graph boost for chunks whose entities match query tokens. Intent is rule-classified (methods / evaluation / limitations / comparison / gaps / recommendations / synthesis).
7. Gaps: interpretable weighted heuristic (see Gap Explorer UI and `services/gaps.py`), renormalised when a signal is missing.
8. Topics: TF-IDF + K-Means (k ≤ 3); <4 papers → one descriptive topic, flagged insufficient. Silhouette reported when computable.
9. Frontend (React + Vite + TypeScript, Cytoscape.js) calls the API only; it holds no paper data of its own.

## Graph schema
Nodes: Paper, ResearchProblem, Method, Dataset, Metric, Finding, Limitation, Domain, ResearchTopic.
Edges: ADDRESSES, USES_METHOD, EVALUATED_ON, MEASURED_BY, REPORTS_FINDING, IDENTIFIES_LIMITATION, RELATED_TO, EXTENDS (reserved; only created with explicit evidence), CONTRADICTS_OR_QUALIFIES (only with a contrast marker + comparative claim in the same chunk).
Every edge stores doc_id, page, snippet, confidence, method, verification status (`heuristic`).

## Security
- Filenames sanitized; uploaded content is never executed.
- API keys only via environment variables, backend only, never logged.
- CORS limited to localhost:5173 in development.
- Text extracted from PDFs is treated as data, never as instructions.
- Pydantic validates all API inputs; file type and size are enforced.

## Replacing a component
Embedder: set `RESEARCHMIND_EMBEDDER=sentence-transformers`. NLP: add spaCy models behind the existing function signatures. Vector store: the Embedder interface (`fit_search`) is the seam — swap in FAISS/ChromaDB without touching routes.
