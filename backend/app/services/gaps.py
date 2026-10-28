"""Interpretable opportunity scoring. Formula from the brief, with
renormalisation when a signal is unavailable. Scores are heuristics,
NOT calibrated probabilities, and outputs are labelled 'potential
opportunities in this collection' — never verified global gaps."""
import hashlib
from collections import Counter, defaultdict

BASE_WEIGHTS = {"underrepresentation": 0.30, "limitation": 0.25, "relationship": 0.20,
                "trend": 0.15, "conflict": 0.10}

def score(signals: dict):
    avail = {k: v for k, v in signals.items() if v is not None}
    if not avail:
        return 0.0, {}
    total = sum(BASE_WEIGHTS[k] for k in avail)
    breakdown = {k: round(BASE_WEIGHTS[k] / total, 3) for k in avail}
    s = 100 * sum((BASE_WEIGHTS[k] / total) * v for k, v in avail.items())
    return round(s, 1), breakdown

def find_gaps(docs, entities, relationships):
    """docs/ entities/ relationships: row dicts. Returns gap dicts."""
    if not docs:
        return []
    total = len(docs)
    by_doc = defaultdict(list)
    for e in entities:
        by_doc[e["doc_id"]].append(e)
    probs = Counter(e["normalized"] for e in entities if e["type"] == "ResearchProblem")
    methods_by_prob = defaultdict(set)
    # Method coverage per problem is approximated via same-document co-occurrence.
    for doc_id, ents in by_doc.items():
        ps = [e["normalized"] for e in ents if e["type"] == "ResearchProblem"]
        ms = [e["normalized"] for e in ents if e["type"] == "Method"]
        for p in ps:
            methods_by_prob[p].update(ms)
    lim_docs = Counter(e["doc_id"] for e in entities if e["type"] == "Limitation")
    conflict = sum(1 for r in relationships if r["relation"] == "CONTRADICTS_OR_QUALIFIES")
    years = [d["year"] for d in docs if d.get("year")]
    recent_share = (sum(1 for y in years if y and y >= 2023) / len(years)) if years else None

    gaps = []
    # Candidate 1: a problem seen in >=1 paper with few methods tried.
    all_methods = {e["normalized"] for e in entities if e["type"] == "Method"}
    for prob, cnt in probs.items():
        coverage = len(methods_by_prob.get(prob, set()))
        under = 1.0 - (coverage / max(1, len(all_methods))) if all_methods else None
        # Limitation evidence: share of docs mentioning any limitation
        lim_ev = (len(lim_docs) / total) if total else 0.0
        # Relationship signal: weak = problem has few distinct method links
        rel_sig = 1.0 - min(1.0, coverage / 3.0)
        signals = {"underrepresentation": under, "limitation": lim_ev,
                   "relationship": rel_sig, "trend": recent_share,
                   "conflict": min(1.0, conflict / max(1, total)) if conflict else 0.0}
        s, breakdown = score(signals)
        ev_docs = [d for d in docs if any(e["normalized"] == prob for e in by_doc[d["id"]])]
        key = hashlib.sha256(f"prob:{prob}".encode()).hexdigest()[:12]
        gaps.append({
            "key": key, "title": f"Underexplored methods for {prob}",
            "problem": prob, "why": f"'{prob}' appears in {cnt} paper(s) but only {coverage} distinct method(s) are linked to it in this collection.",
            "papers": [{"id": d["id"], "title": d["title"]} for d in ev_docs],
            "evidence": [e["snippet"] for e in entities if e["normalized"] == prob][:3],
            "methods": sorted(methods_by_prob.get(prob, set())),
            "datasets": sorted({e["name"] for e in entities if e["type"] == "Dataset"}),
            "limitations": [e["name"] for e in entities if e["type"] == "Limitation"][:5],
            "proposed_question": f"How do alternative methods compare on {prob} under a common evaluation?",
            "proposed_experiment": f"Benchmark at least two methods not yet linked to {prob} in this collection on a shared dataset, reporting the metrics already used by these papers.",
            "metrics": sorted({e["name"] for e in entities if e["type"] == "Metric"}),
            "score": s, "breakdown": breakdown, "signals": signals,
            "confidence": "low" if total < 3 else "medium",
            "caveat": "Potential opportunity in THIS collection only. Absence here is not proof of a global gap; verify against broader literature before claiming novelty."})
    # Candidate 2: repeated limitation as its own opportunity
    lim_counts = Counter(e["normalized"] for e in entities if e["type"] == "Limitation")
    for lim, cnt in lim_counts.most_common(3):
        if cnt < 1:
            continue
        signals = {"underrepresentation": 0.5, "limitation": min(1.0, cnt / total),
                   "relationship": 0.5, "trend": recent_share, "conflict": 0.0}
        s, breakdown = score(signals)
        key = hashlib.sha256(f"lim:{lim}".encode()).hexdigest()[:12]
        gaps.append({"key": key, "title": f"Address the repeated limitation: {lim[:60]}",
                     "problem": lim, "why": f"This limitation recurs across {cnt} paper(s) in the collection.",
                     "papers": [], "evidence": [e["snippet"] for e in entities if e["normalized"] == lim][:3],
                     "methods": [], "datasets": [], "limitations": [lim],
                     "proposed_question": f"Can a method be designed that avoids: {lim[:80]}?",
                     "proposed_experiment": "Design a study that isolates this limitation as its primary variable and reports whether the new approach removes it.",
                     "metrics": [], "score": s, "breakdown": breakdown, "signals": signals,
                     "confidence": "low" if total < 3 else "medium",
                     "caveat": "Potential opportunity in THIS collection only."})
    gaps.sort(key=lambda g: -g["score"])
    return gaps
