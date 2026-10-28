"""PDF extraction with PyMuPDF. Scanned PDFs are flagged, never faked."""
try:
    import pymupdf as fitz  # PyMuPDF
except ImportError:
    import fitz

def extract_pages(path: str):
    """Return (pages, scanned, page_count). pages=[{page:int,text:str}]."""
    doc = fitz.open(path)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text("text") or ""
        pages.append({"page": i + 1, "text": text})
    doc.close()
    # A page is effectively empty if it yields almost no extractable text.
    empty = sum(1 for p in pages if len(p["text"].strip()) < 20)
    scanned = bool(pages) and empty / len(pages) >= 0.8
    return pages, scanned, len(pages)

def extract_metadata(pages):
    """Heuristic, documented metadata. Unknown fields stay None/empty."""
    full = "\n".join(p["text"] for p in pages)
    lines = [ln.strip() for ln in full.splitlines() if ln.strip()]
    title = lines[0] if lines else None
    # Title is usually the first substantial line; drop a leading header.
    if title and len(title) < 8 and len(lines) > 1:
        title = lines[1]
    abstract = ""
    low = full.lower()
    if "abstract" in low:
        start = low.index("abstract") + len("abstract")
        abstract = full[start:start + 1200].strip().split("\n\n")[0].strip()
    year = None
    import re
    m = re.search(r"\b(19|20)\d{2}\b", full[:4000])
    if m:
        year = int(m.group(0))
    keywords = []
    if "keywords" in low:
        seg = full[low.index("keywords"):low.index("keywords") + 400]
        keywords = [k.strip() for k in seg.replace("Keywords", "").replace(":", "").split(",") if k.strip()][:10]
    return {"title": title, "abstract": abstract or None, "year": year, "keywords": keywords}
