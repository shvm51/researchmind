# API documentation (also at /docs via FastAPI OpenAPI)

- GET /health — server + DB path
- GET /api/stats — real counts + recent papers
- POST /api/documents/upload — multipart `files` (PDFs only); returns per-file status, `duplicate_of_existing` on hash match
- GET /api/documents[?q=&status=] — list
- GET /api/documents/{id} — detail + entities + chunk count
- GET /api/documents/{id}/file — original PDF
- DELETE /api/documents/{id} — cascade delete
- POST /api/documents/{id}/reprocess
- GET /api/graph[?node_type=&relation=&q=&paper_id=] — nodes/edges (max 500/1000, `truncated` flag)
- POST /api/ask {question, paper_ids?, top_k?} — {intent, answer, citations[{title, page, snippet, score}], llm_used, mode}
- GET /api/gaps — scored opportunities with breakdown, signals, caveat
- POST /api/gaps/{key}/feedback {verdict: useful|irrelevant|already_investigated} — ranking preference only
- GET /api/topics — K-Means clusters or insufficient flag
- GET /api/recommendations?paper_id= — ranked papers with explanations
- POST /api/evaluate — measured semantic vs graph vs hybrid comparison (token-overlap proxy + latency; see EVALUATION.md)
