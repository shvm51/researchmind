"""Embeddings: TF-IDF by default (deterministic, no download).
sentence-transformers is used only if RESEARCHMIND_EMBEDDER=sentence-transformers
and the package + model load; otherwise the fallback is reported honestly."""
import os, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class Embedder:
    def __init__(self):
        self.kind = "tfidf"
        self.vec = None
        if os.environ.get("RESEARCHMIND_EMBEDDER") == "sentence-transformers":
            try:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer(os.environ.get("RESEARCHMIND_ST_MODEL", "all-MiniLM-L6-v2"))
                self.kind = "sentence-transformers"
            except Exception as e:
                self.kind = "tfidf (sentence-transformers unavailable: %s)" % str(e)[:80]

    def fit_search(self, query: str, docs: list):
        """Return [(index, score)] ranked by cosine similarity."""
        if not docs:
            return []
        if self.kind.startswith("sentence-transformers"):
            import numpy as np
            q = self.model.encode([query], normalize_embeddings=True)
            d = self.model.encode(docs, normalize_embeddings=True)
            scores = (d @ q[0])
            return sorted(enumerate(scores.tolist()), key=lambda x: -x[1])
        self.vec = TfidfVectorizer(stop_words="english", max_features=5000)
        mat = self.vec.fit_transform(docs + [query])
        sims = cosine_similarity(mat[-1], mat[:-1])[0]
        return sorted(enumerate(sims.tolist()), key=lambda x: -x[1])
