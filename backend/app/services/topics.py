"""Topic discovery: TF-IDF + K-Means, graceful on small collections.
No forced clusters: <4 docs -> one descriptive topic + insufficient flag."""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import numpy as np

def discover_topics(docs):
    """docs: [{id,title,abstract,text}]. Returns {topics, insufficient, note}."""
    texts = [(d.get("abstract") or "") + " " + (d.get("text") or "") for d in docs]
    if len(docs) < 2:
        return {"topics": [], "insufficient": True,
                "note": "Need at least 2 papers for topic discovery."}
    if len(docs) < 4:
        return {"topics": [{"id": 0, "keywords": ["collection too small for clustering"],
                            "papers": [d["id"] for d in docs], "size": len(docs),
                            "summary": "Single descriptive topic: the collection is too small to split meaningfully."}],
                "insufficient": True,
                "note": "Fewer than 4 papers: clustering is not forced; this is one descriptive topic."}
    vec = TfidfVectorizer(stop_words="english", max_features=1000)
    X = vec.fit_transform(texts)
    k = min(3, len(docs) - 1)
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)
    terms = np.array(vec.get_feature_names_out())
    topics = []
    for c in range(k):
        idx = [i for i, lab in enumerate(km.labels_) if lab == c]
        centroid = km.cluster_centers_[c]
        top = terms[np.argsort(centroid)[-6:][::-1]].tolist()
        # Representative paper: nearest to centroid
        rep = idx[int(np.argmin(((X[idx].toarray() - centroid) ** 2).sum(axis=1)))] if idx else None
        topics.append({"id": c, "keywords": top, "papers": [docs[i]["id"] for i in idx],
                       "size": len(idx), "representative": docs[rep]["id"] if rep is not None else None,
                       "summary": f"Cluster around: {', '.join(top[:3])}."})
    sil = None
    try:
        sil = round(float(silhouette_score(X, km.labels_)), 3)
    except Exception:
        pass
    return {"topics": topics, "insufficient": False, "silhouette": sil,
            "note": f"K-Means k={k} on TF-IDF. Silhouette={sil} (higher is better; low values mean weak separation)."}
