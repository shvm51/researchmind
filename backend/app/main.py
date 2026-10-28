"""ResearchMind API. All stats come from SQLite; no fake numbers.
Deleting a document cascades to its chunks/entities/relationships."""
import os, re, shutil, uuid, time
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .config import DATA_DIR, UPLOAD_DIR, MAX_UPLOAD_MB
from . import db
from .services import pdf_extract, chunking, nlp
from .services.retrieval import classify_intent, hybrid_search
from .services import llm as llm_mod, gaps as gaps_mod, topics as topics_mod, recommendations as rec_mod

app = FastAPI(title="ResearchMind", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_origin_regex=r"https://.*\.vercel\.app",
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
db.init_db()

# ---------- helpers ----------
def rows(sql, args=()):
    c = db.connect(); r = [dict(x) for x in c.execute(sql, args).fetchall()]; c.close(); return r
def row(sql, args=()):
    c = db.connect(); r = c.execute(sql, args).fetchone(); c.close(); return dict(r) if r else None
def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", Path(name).name)[:120]

def process_file(doc_id: str, path: str, filename: str, data: bytes):
    c = db.connect()
    try:
        pages, scanned, pc = pdf_extract.extract_pages(path)
        if scanned:
            c.execute("UPDATE documents SET status=?, error=?, page_count=? WHERE id=?",
                      ("failed", "Scanned / unreadable PDF: no extractable text on most pages. OCR is an optional extension and was not silently applied.", pc, doc_id))
            c.commit(); return
        meta = pdf_extract.extract_metadata(pages)
        all_chunks = []
        for p in pages:
            all_chunks += chunking.chunk_page(p["text"], p["page"])
        c.execute("UPDATE documents SET title=?, year=?, abstract=?, keywords=?, status=?, page_count=? WHERE id=?",
                  (meta["title"], meta["year"], meta["abstract"], ",".join(meta["keywords"]), "done", pc, doc_id))
        c.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
        c.execute("DELETE FROM entities WHERE doc_id=?", (doc_id,))
        c.execute("DELETE FROM relationships WHERE doc_id=?", (doc_id,))
        for i, ch in enumerate(all_chunks):
            c.execute("INSERT INTO chunks VALUES (?,?,?,?,?)", (f"{doc_id}:c{i}", doc_id, ch["page"], ch["offset_chars"], ch["text"]))
        ents, rels = nlp.extract_entities(all_chunks)
        for i, e in enumerate(ents):
            c.execute("INSERT INTO entities VALUES (?,?,?,?,?,?,?,?,?)",
                      (f"{doc_id}:e{i}", doc_id, e["type"], e["name"], e["normalized"], e["page"], e["snippet"], e["confidence"], e["method"]))
        for i, (st, rel, tt, tgt, conf, src_ent) in enumerate(rels):
            src_name = row_title(doc_id) if st == "Paper" else (src_ent or "")
            c.execute("INSERT INTO relationships VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                      (f"{doc_id}:r{i}", doc_id, st, src_name, rel, tt, tgt["name"], tgt["page"], tgt["snippet"], conf, tgt["method"], "heuristic"))
        # Fix Paper source name (needs title already set)
        title = meta["title"] or filename
        c.execute("UPDATE relationships SET source_name=? WHERE doc_id=? AND source_type='Paper'", (title, doc_id))
        c.commit()
    except Exception as e:
        c.execute("UPDATE documents SET status=?, error=? WHERE id=?", ("failed", str(e)[:500], doc_id)); c.commit()
    finally:
        c.close()

def row_title(doc_id):
    d = row("SELECT title FROM documents WHERE id=?", (doc_id,))
    return d["title"] if d else doc_id

# ---------- models ----------
class AskReq(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    paper_ids: list[str] = []
    top_k: int = 8
class FeedbackReq(BaseModel):
    verdict: str = Field(pattern="^(useful|irrelevant|already_investigated)$")

# ---------- routes ----------
@app.get("/health")
def health():
    return {"status": "ok", "db": str(db.DB_PATH)}

@app.get("/api/stats")
def stats():
    docs = rows("SELECT * FROM documents")
    return {
        "total_papers": len(docs),
        "processed_papers": sum(1 for d in docs if d["status"] == "done"),
        "failed_papers": sum(1 for d in docs if d["status"] == "failed"),
        "entities": row("SELECT COUNT(*) n FROM entities")["n"],
        "relationships": row("SELECT COUNT(*) n FROM relationships")["n"],
        "chunks": row("SELECT COUNT(*) n FROM chunks")["n"],
        "limitations": row("SELECT COUNT(*) n FROM entities WHERE type='Limitation'")["n"],
        "recent": rows("SELECT id,title,status,created_at FROM documents ORDER BY created_at DESC LIMIT 10"),
    }

@app.post("/api/documents/upload")
async def upload(files: list[UploadFile] = File(...)):
    out = []
    for f in files:
        data = await f.read()
        if not f.filename.lower().endswith(".pdf"):
            raise HTTPException(400, f"{f.filename}: only PDF files are accepted")
        if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
            raise HTTPException(400, f"{f.filename}: exceeds {MAX_UPLOAD_MB} MB limit")
        h = db.sha256_bytes(data)
        dup = row("SELECT id FROM documents WHERE sha256=?", (h,))
        if dup:
            out.append({"id": dup["id"], "duplicate_of_existing": True, "status": "duplicate"}); continue
        doc_id = uuid.uuid4().hex[:12]
        path = UPLOAD_DIR / f"{doc_id}_{safe_name(f.filename)}"
        path.write_bytes(data)
        c = db.connect()
        c.execute("INSERT INTO documents (id,title,filename,sha256,status) VALUES (?,?,?,?,?)",
                  (doc_id, None, f.filename, h, "processing"))
        c.commit(); c.close()
        process_file(doc_id, str(path), f.filename, data)
        out.append({"id": doc_id, "status": row("SELECT status FROM documents WHERE id=?", (doc_id,))["status"]})
    return {"uploaded": out}

@app.get("/api/documents")
def list_docs(q: str = "", status: str = ""):
    docs = rows("SELECT * FROM documents ORDER BY created_at DESC")
    if q:
        docs = [d for d in docs if q.lower() in (d["title"] or "").lower() or q.lower() in (d["filename"] or "").lower()]
    if status:
        docs = [d for d in docs if d["status"] == status]
    return docs

@app.get("/api/documents/{doc_id}")
def get_doc(doc_id: str):
    d = row("SELECT * FROM documents WHERE id=?", (doc_id,))
    if not d: raise HTTPException(404, "Document not found")
    d["entities"] = rows("SELECT * FROM entities WHERE doc_id=?", (doc_id,))
    d["chunks_count"] = row("SELECT COUNT(*) n FROM chunks WHERE doc_id=?", (doc_id,))["n"]
    return d

@app.get("/api/documents/{doc_id}/file")
def get_file(doc_id: str):
    d = row("SELECT * FROM documents WHERE id=?", (doc_id,))
    if not d: raise HTTPException(404, "Document not found")
    for p in UPLOAD_DIR.glob(f"{doc_id}_*"):
        return FileResponse(str(p), media_type="application/pdf", filename=d["filename"])
    raise HTTPException(404, "Stored PDF not found")

@app.delete("/api/documents/{doc_id}")
def delete_doc(doc_id: str):
    d = row("SELECT * FROM documents WHERE id=?", (doc_id,))
    if not d: raise HTTPException(404, "Document not found")
    c = db.connect(); c.execute("DELETE FROM documents WHERE id=?", (doc_id,)); c.commit(); c.close()
    for p in UPLOAD_DIR.glob(f"{doc_id}_*"):
        p.unlink(missing_ok=True)
    return {"deleted": doc_id}

@app.post("/api/documents/{doc_id}/reprocess")
def reprocess(doc_id: str):
    d = row("SELECT * FROM documents WHERE id=?", (doc_id,))
    if not d: raise HTTPException(404, "Document not found")
    paths = list(UPLOAD_DIR.glob(f"{doc_id}_*"))
    if not paths: raise HTTPException(404, "Stored PDF not found")
    process_file(doc_id, str(paths[0]), d["filename"], b"")
    return {"id": doc_id, "status": row("SELECT status FROM documents WHERE id=?", (doc_id,))["status"]}

@app.get("/api/graph")
def graph(node_type: str = "", relation: str = "", q: str = "", paper_id: str = ""):
    rels = rows("SELECT * FROM relationships" + (" WHERE doc_id=?" if paper_id else ""), (paper_id,) if paper_id else ())
    nodes, edges, seen = [], [], set()
    def add_node(ntype, name):
        key = (ntype, name)
        if key not in seen:
            seen.add(key); nodes.append({"id": f"{ntype}:{name}", "type": ntype, "label": name})
    for r in rels:
        if node_type and r["target_type"] != node_type and r["source_type"] != node_type: continue
        if relation and r["relation"] != relation: continue
        if q and q.lower() not in r["target_name"].lower() and q.lower() not in (r["source_name"] or "").lower(): continue
        src = r["source_name"] or "Paper"
        add_node(r["source_type"], src); add_node(r["target_type"], r["target_name"])
        edges.append({"id": r["id"], "source": f"{r['source_type']}:{src}", "target": f"{r['target_type']}:{r['target_name']}",
                      "label": r["relation"], "doc_id": r["doc_id"], "page": r["page"], "snippet": r["snippet"],
                      "confidence": r["confidence"], "method": r["method"]})
    return {"nodes": nodes[:500], "edges": edges[:1000], "truncated": len(nodes) > 500 or len(edges) > 1000}

@app.post("/api/ask")
def ask(req: AskReq):
    intent = classify_intent(req.question)
    chunks = rows("SELECT * FROM chunks" + (" WHERE doc_id IN (%s)" % ",".join("?" * len(req.paper_ids)) if req.paper_ids else ""), tuple(req.paper_ids))
    ents = rows("SELECT * FROM entities")
    hits = hybrid_search(req.question, chunks, ents, top_k=req.top_k)
    docs = {d["id"]: d for d in rows("SELECT * FROM documents")}
    citations = [{"paper_id": h["doc_id"], "title": docs.get(h["doc_id"], {}).get("title") or "Unknown",
                  "page": h["page"], "snippet": h["text"][:400], "score": h["score"]} for h in hits]
    answer, llm_used, mode = llm_mod.synthesize(req.question, citations, intent)
    c = db.connect()
    import json as _j
    c.execute("INSERT INTO questions (question,intent,answer,citations) VALUES (?,?,?,?)",
              (req.question, intent, answer, _j.dumps(citations))); c.commit(); c.close()
    return {"intent": intent, "answer": answer, "citations": citations,
            "llm_used": llm_used, "mode": mode,
            "note": "Author findings vs ResearchMind interpretation are separated in the answer text."}

@app.get("/api/gaps")
def get_gaps():
    docs = rows("SELECT * FROM documents WHERE status='done'")
    ents = rows("SELECT * FROM entities"); rels = rows("SELECT * FROM relationships")
    gaps = gaps_mod.find_gaps(docs, ents, rels)
    fb = {r["gap_key"]: r["verdict"] for r in rows("SELECT * FROM gap_feedback")}
    for g in gaps:
        g["feedback"] = fb.get(g["key"])
    # Feedback re-ranks: useful up, irrelevant down (preference only, no retraining claim)
    for g in gaps:
        if g["feedback"] == "useful": g["score"] = min(100.0, g["score"] + 5)
        if g["feedback"] == "irrelevant": g["score"] = max(0.0, g["score"] - 10)
    gaps.sort(key=lambda x: -x["score"])
    return gaps

@app.post("/api/gaps/{key}/feedback")
def gap_feedback(key: str, req: FeedbackReq):
    c = db.connect()
    c.execute("INSERT OR REPLACE INTO gap_feedback VALUES (?,?,CURRENT_TIMESTAMP)", (key, req.verdict)); c.commit(); c.close()
    return {"key": key, "verdict": req.verdict, "note": "Ranking preference only; the model has not been retrained."}

@app.get("/api/topics")
def get_topics():
    docs = rows("SELECT * FROM documents WHERE status='done'")
    full = []
    for d in docs:
        txt = " ".join(c["text"] for c in rows("SELECT text FROM chunks WHERE doc_id=?", (d["id"],)))[:6000]
        full.append({**d, "text": txt})
    res = topics_mod.discover_topics(full)
    titles = {d["id"]: d["title"] for d in docs}
    for t in res["topics"]:
        t["paper_titles"] = [titles.get(p) for p in t["papers"]]
    return res

@app.get("/api/recommendations")
def get_recs(paper_id: str):
    docs = rows("SELECT * FROM documents WHERE status='done'")
    if not any(d["id"] == paper_id for d in docs): raise HTTPException(404, "Paper not found")
    chunks = rows("SELECT * FROM chunks"); ents = rows("SELECT * FROM entities")
    return rec_mod.recommend(paper_id, docs, chunks, ents)

@app.post("/api/evaluate")
def evaluate():
    """Measured (not fabricated) comparison: semantic vs graph vs hybrid.
    Success = top-5 hits share a token with the query (documented proxy)."""
    import time
    chunks = rows("SELECT * FROM chunks"); ents = rows("SELECT * FROM entities")
    queries = ["methods for question answering", "limitations of transformer models", "datasets and metrics"]
    out = []
    for q in queries:
        row_out = {"query": q}
        for mode in ["semantic", "graph", "hybrid"]:
            t0 = time.time()
            if mode == "semantic":
                from .services.embeddings import Embedder
                emb = Embedder(); ranked = emb.fit_search(q, [c["text"] for c in chunks])[:5]
                hits = [chunks[i] for i, _ in ranked]
            elif mode == "graph":
                hits = [c for c in chunks if any(e["normalized"] in c["text"].lower() for e in ents)][:5]
            else:
                hits = hybrid_search(q, chunks, ents, top_k=5)
            qt = set(q.split())
            supported = sum(1 for h in hits if qt & set(h["text"].lower().split()))
            row_out[mode] = {"hits": len(hits), "token_supported": supported,
                             "latency_ms": round((time.time() - t0) * 1000, 1)}
        out.append(row_out)
    return {"results": out, "note": "Token-overlap proxy only; manually review a sample of relations and gaps before claiming improvement."}
