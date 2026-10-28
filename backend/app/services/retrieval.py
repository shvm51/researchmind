"""Hybrid retrieval + intent routing. Rules are explicit and testable."""
import re
from .embeddings import Embedder

def classify_intent(q: str) -> str:
    low = q.lower()
    if any(w in low for w in ["limitation", "limitation", "weakness", "fail"]):
        return "limitations"
    if any(w in low for w in ["dataset", "metric", "evaluat"]):
        return "evaluation"
    if any(w in low for w in ["method", "approach", "technique", "how"]):
        return "methods"
    if any(w in low for w in ["differ", "compare", "versus", "vs", "contrast"]):
        return "comparison"
    if any(w in low for w in ["gap", "future", "direction", "opportunit", "next step"]):
        return "gaps"
    if any(w in low for w in ["which paper", "recommend", "relevant paper"]):
        return "recommendations"
    return "synthesis"

def hybrid_search(query: str, chunks, entities, top_k: int = 8):
    """Semantic (TF-IDF cosine) + graph boost: chunks whose entities match
    query tokens get +0.15 per matching entity type, capped. Returns ranked chunks."""
    if not chunks:
        return []
    texts = [c["text"] for c in chunks]
    emb = Embedder()
    ranked = dict(emb.fit_search(query, texts))
    qtokens = set(re.findall(r"[a-z]{3,}", query.lower()))
    out = []
    for idx, ch in enumerate(chunks):
        score = float(ranked.get(idx, 0.0))
        # Graph boost: entity names appearing in both query and chunk
        matches = 0
        for e in entities:
            if e["doc_id"] == ch["doc_id"] and e["normalized"] in ch["text"].lower():
                if any(t in e["normalized"] for t in qtokens):
                    matches += 1
        score = min(1.0, score + 0.10 * min(matches, 3))
        out.append({**ch, "score": round(score, 4), "graph_matches": matches})
    out.sort(key=lambda x: -x["score"])
    return out[:top_k]
