"""LLM provider abstraction. Default provider is 'none': answers are
extractive syntheses from cited evidence, never presented as LLM output.
If an OpenAI-compatible provider is configured, only short evidence snippets
are sent, with a timeout, and any failure falls back to the extractive answer."""
import os, json, urllib.request
from ..config import LLM_PROVIDER, LLM_MODEL, LLM_API_KEY

def synthesize(question: str, evidence: list, intent: str):
    """evidence: [{title, page, snippet}]. Returns (answer, llm_used, mode)."""
    if not evidence:
        return ("The uploaded collection does not provide enough information to answer this question.",
                False, "insufficient-evidence")
    lines = [f"Based on the uploaded papers ({intent} question):"]
    for ev in evidence[:5]:
        lines.append(f"- {ev['title']} (p. {ev['page']}): {ev['snippet'][:300]}")
    lines.append("\nFindings above are reported by the paper authors; any synthesis "
                 "sentence here is ResearchMind's interpretation of those cited snippets.")
    extractive = "\n".join(lines)
    if LLM_PROVIDER == "none" or not LLM_API_KEY:
        return extractive, False, "extractive_fallback (no LLM configured)"
    try:
        body = json.dumps({"model": LLM_MODEL or "gpt-4o-mini",
                           "messages": [{"role": "system", "content": "Answer ONLY from the evidence snippets. Cite paper title and page for each claim. If evidence is insufficient, say so."},
                                        {"role": "user", "content": f"Question: {question}\nEvidence:\n" + "\n".join(f"{e['title']} p.{e['page']}: {e['snippet'][:500]}" for e in evidence[:5])}],
                           "temperature": 0.2}).encode()
        req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=body,
                                     headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        return data["choices"][0]["message"]["content"], True, f"llm:{LLM_PROVIDER}/{LLM_MODEL}"
    except Exception as e:
        return extractive + f"\n\n[LLM unavailable ({type(e).__name__}); showing extractive fallback.]", False, "extractive_fallback (llm error)"
