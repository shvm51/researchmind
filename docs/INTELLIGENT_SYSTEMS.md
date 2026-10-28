# Intelligent Systems concepts demonstrated

- NLP: PDF preprocessing, metadata heuristics, pattern/lexicon entity and relation extraction (`services/nlp.py`).
- Knowledge representation: typed graph schema, provenance (doc/page/snippet/method/confidence), normalization without similarity merging (`ARCHITECTURE.md`).
- Intelligent search: embedding retrieval, graph traversal/boost, rule-based query-intent routing, hybrid ranking (`services/retrieval.py`).
- Rule-based reasoning: repeated limitations, underexplored problem×method coverage, conflict detection with explicit evidence requirements (`services/gaps.py`, `services/nlp.py`).
- Machine learning: TF-IDF representations, K-Means topic clustering, silhouette quality where computable, similarity ranking (`services/topics.py`, `services/embeddings.py`).
- Heuristic decision support: transparent opportunity score with renormalised weights and per-signal breakdown (`services/gaps.py`).
- Explainable AI: every claim carries citations; graph paths and score breakdowns are inspectable; author findings are separated from ResearchMind interpretations in assistant answers.
