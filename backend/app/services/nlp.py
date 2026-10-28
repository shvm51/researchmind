"""Deterministic heuristic NLP. spaCy is optional; regex fallback is the default
so the system works with no model download. Every entity keeps its snippet,
page and method so a human can audit it. No entity is merged on similarity
alone: deduplication is exact on the normalized name only."""
import re

METRICS = ["accuracy", "f1-score", "f1 score", "precision", "recall", "bleu", "rouge", "auc", "mse", "mae"]
METHOD_CUES = ["transformer", "bert", "cnn", "convolutional neural network", "lstm", "random forest",
               "support vector machine", "svm", "gradient boosting", "neural network", "graph neural network",
               "reinforcement learning", "attention mechanism", "fine-tuning", "fine tuning"]
DATASET_CUES = ["dataset", "benchmark", "corpus"]
LIMIT_WORDS = ["limitation", "limitations", "fails", "failure", "limited to", "future work", "shortcoming"]
CONTRAST_WORDS = ["however", "in contrast", "although", "nevertheless", "outperforms", "underperforms"]

def normalize(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower().strip(" .,:;()[]"))

def _cap_phrases(text: str):
    # Capitalised 2-3 word phrases, e.g. "ImageNet Dataset", "Question Answering".
    return re.findall(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b", text)

def extract_entities(chunks):
    """chunks: list of dicts with page/text. Returns (entities, relationships)."""
    entities, rels = [], []
    seen = set()
    def add(doc_type, name, page, snippet, conf, method):
        n = normalize(name)
        if not n or len(n) < 3:
            return None
        key = (doc_type, n)
        if key in seen:
            return None
        seen.add(key)
        e = {"type": doc_type, "name": name.strip(), "normalized": n, "page": page,
             "snippet": snippet[:400], "confidence": conf, "method": method}
        entities.append(e)
        return e

    for ch in chunks:
        text, page = ch["text"], ch["page"]
        low = text.lower()
        # Methods: lexicon + "using X" / "we propose X" patterns
        for m in METHOD_CUES:
            if m in low:
                add("Method", m.title() if m.islower() else m, page, text, 0.75, "lexicon")
        for pat in [r"using (?:the )?([A-Z][\w\- ]{2,40}?)(?: model| approach| method| architecture)?\b",
                    r"we propose (?:a |an |the )?([A-Z][\w\- ]{2,40}?)(?: model| approach| method)?\b"]:
            for mm in re.finditer(pat, text):
                add("Method", mm.group(1), page, text, 0.65, "pattern:using/propose")
        # Datasets: "on the X dataset/benchmark"
        for mm in re.finditer(r"(?:on|using) (?:the )?([A-Z][\w\-]{2,30})(?: dataset| benchmark| corpus)", text):
            add("Dataset", mm.group(1), page, text, 0.8, "pattern:dataset")
        # Metrics
        for m in METRICS:
            if m in low:
                add("Metric", m.upper() if len(m) <= 4 else m.title(), page, text, 0.8, "lexicon")
        # Findings: improvement / result sentences
        if re.search(r"(improv|outperform|achiev|accuracy of|f1|results show)", low):
            # Finding name = short clause, not the whole chunk
            sent = re.split(r"(?<=[.!?])\s+", text)[0]
            add("Finding", sent[:90], page, text, 0.6, "pattern:result-sentence")
        # Limitations
        if any(w in low for w in LIMIT_WORDS):
            sent = re.split(r"(?<=[.!?])\s+", text)[0]
            add("Limitation", sent[:90], page, text, 0.7, "pattern:limitation-sentence")
        # Research problem: "problem of X" / "task of X"
        for mm in re.finditer(r"(?:problem|task) of ([a-z][\w ]{3,40}?)(?:\.|,| is| involves)", low):
            add("ResearchProblem", mm.group(1), page, text, 0.65, "pattern:problem-of")
        # Domain from title-ish keywords
        for dom, words in [("Natural Language Processing", ["language", "text", "nlp"]),
                           ("Computer Vision", ["image", "vision", "visual"]),
                           ("Healthcare", ["medical", "patient", "disease", "clinical"])]:
            if any(w in low for w in words):
                add("Domain", dom, page, text, 0.55, "lexicon:domain")

    # Relationships: paper-level links + same-chunk co-occurrence (conservative).
    by_type = {}
    for e in entities:
        by_type.setdefault(e["type"], []).append(e)
    for prob in by_type.get("ResearchProblem", []):
        rels.append(("Paper", "ADDRESSES", "ResearchProblem", prob, 0.7, None))
    for m in by_type.get("Method", []):
        rels.append(("Paper", "USES_METHOD", "Method", m, 0.75, None))
    for d in by_type.get("Dataset", []):
        rels.append(("Paper", "EVALUATED_ON", "Dataset", d, 0.8, None))
    for met in by_type.get("Metric", []):
        rels.append(("Paper", "MEASURED_BY", "Metric", met, 0.8, None))
    for f in by_type.get("Finding", []):
        rels.append(("Paper", "REPORTS_FINDING", "Finding", f, 0.6, None))
    for lim in by_type.get("Limitation", []):
        rels.append(("Paper", "IDENTIFIES_LIMITATION", "Limitation", lim, 0.7, None))
    # RELATED_TO only for same-chunk method+dataset co-occurrence.
    for ch in chunks:
        low = ch["text"].lower()
        ms = [e for e in by_type.get("Method", []) if normalize(e["name"]) in low]
        ds = [e for e in by_type.get("Dataset", []) if normalize(e["name"]) in low]
        for m in ms:
            for d in ds:
                rels.append(("Method", "RELATED_TO", "Dataset", d, 0.6, m["name"]))
    # CONTRADICTS_OR_QUALIFIES: only with an explicit contrast marker AND a
    # comparative claim in the same chunk. Similarity alone never creates it.
    for ch in chunks:
        low = ch["text"].lower()
        if any(w in low for w in CONTRAST_WORDS) and re.search(r"(outperform|underperform|better than|worse than)", low):
            fs = by_type.get("Finding", [])
            if fs:
                rels.append(("Finding", "CONTRADICTS_OR_QUALIFIES", "Finding", fs[0], 0.55, fs[0]["name"]))
    return entities, rels
