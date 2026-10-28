"""Recommendations: shared entities + semantic similarity + centrality.
Every recommendation carries a plain-language explanation."""
from .embeddings import Embedder

def recommend(paper_id, docs, chunks, entities):
    by_doc = {}
    for e in entities:
        by_doc.setdefault(e["doc_id"], set()).add((e["type"], e["normalized"]))
    target = by_doc.get(paper_id, set())
    texts = {}
    for d in docs:
        texts[d["id"]] = " ".join(c["text"] for c in chunks if c["doc_id"] == d["id"])[:4000]
    sims = {}
    if paper_id in texts and len(texts) > 1:
        emb = Embedder()
        others = [k for k in texts if k != paper_id]
        ranked = dict(emb.fit_search(texts[paper_id], [texts[k] for k in others]))
        sims = {others[i]: float(s) for i, s in ranked.items()}
    out = []
    for d in docs:
        if d["id"] == paper_id:
            continue
        shared = target & by_doc.get(d["id"], set())
        shared_methods = [n for t, n in shared if t == "Method"]
        shared_topics = [n for t, n in shared if t != "Method"]
        s = 0.5 * len(shared) / max(1, len(target)) + 0.5 * sims.get(d["id"], 0.0)
        out.append({"paper": d, "score": round(float(s), 3),
                    "shared_entities": sorted(shared),
                    "explanation": f"Shares {len(shared)} entit{'y' if len(shared)==1 else 'ies'}"
                                   f"{' including methods: ' + ', '.join(shared_methods) if shared_methods else ''}; "
                                   f"semantic similarity {sims.get(d['id'], 0.0):.2f}."})
    out.sort(key=lambda x: -x["score"])
    return out
