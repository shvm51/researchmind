# Evaluation procedure

Run `POST /api/evaluate` on your own collection, or `pytest` for the synthetic fixture suite.

## Method
Three retrieval modes are compared on the same queries: semantic (TF-IDF cosine),
graph (entity-match chunks), hybrid (semantic + graph boost). For each mode the
endpoint reports hit count, token-supported hits (a documented proxy, not a
claim of correctness), and latency in ms.

## What to review manually (required before any improvement claim)
1. A sample of extracted relationships: open each edge's snippet and originating paper.
2. A sample of gap cards: check that evidence snippets actually support the title.
3. A sample of answers: check every citation's page and snippet against the PDF.

## Rules
- Do not report a benchmark number from this proxy as answer correctness.
- Do not claim hybrid beats semantic/graph unless the measured run on a stated
  dataset, with stated queries, shows it — and state the dataset and queries.
- Synthetic fixtures in `backend/tests/` are labelled as such and are never
  presented as real research findings.

## Current measured result
- Backend test suite (synthetic 3-paper fixture, 2026-10-28): 3 passed.
  The suite asserts retrieval returns citations, graph edges exist, gaps score
  in [0,100] with a renormalised breakdown, recommendations carry explanations,
  duplicates are detected, and delete cascades to zero edges.
- No benchmark improvement is claimed: `/api/evaluate` output is a live
  measurement on whatever collection is uploaded, not a published result.
