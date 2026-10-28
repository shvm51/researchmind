import re

def chunk_page(text: str, page: int, max_chars: int = 900):
    """Sentence-aware chunks that preserve page + char offset (provenance)."""
    sentences = re.split(r"(?<=[.!?])\s+", text.replace("\n", " ").strip())
    chunks, cur, offset = [], "", 0
    for s in sentences:
        if len(cur) + len(s) + 1 > max_chars and cur.strip():
            chunks.append({"page": page, "offset_chars": offset, "text": cur.strip()})
            offset += len(cur) + 1
            cur = s
        else:
            cur = (cur + " " + s).strip() if cur else s
    if cur.strip():
        chunks.append({"page": page, "offset_chars": offset, "text": cur.strip()})
    return chunks
