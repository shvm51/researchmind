import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["RESEARCHMIND_DATA_DIR"] = "/tmp/researchmind_test_data"
import fitz
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
PAPERS = [
    ("Transformer QA", "We propose a transformer model for the problem of question answering. Using the SQuAD dataset, the model achieves accuracy of 92%. A limitation is that it fails on long documents. Future work should address long documents."),
    ("BERT Retrieval", "We use BERT for the problem of question answering. Using the SQuAD dataset, BERT improves accuracy over the baseline. However, BERT underperforms on long documents, a limitation of transformer models."),
    ("CNN Vision", "We propose a CNN model for the problem of image classification. Using the ImageNet dataset, the model achieves accuracy of 88%. A limitation is limited to small images."),
]

def make_pdf(path, title, body):
    doc = fitz.open(); page = doc.new_page()
    page.insert_text((72, 72), f"{title}\n\nAbstract\n{body}\n\nKeywords: test, demo", fontsize=11)
    doc.save(path); doc.close()

def test_upload_ask_graph_gaps():
    for i, (title, body) in enumerate(PAPERS):
        p = f"/tmp/rm_paper{i}.pdf"; make_pdf(p, title, body)
        with open(p, "rb") as fh:
            r = client.post("/api/documents/upload", files=[("files", (f"p{i}.pdf", fh, "application/pdf"))])
        assert r.status_code == 200, r.text
    s = client.get("/api/stats").json()
    assert s["total_papers"] >= 3 and s["processed_papers"] >= 3
    assert s["entities"] > 0 and s["relationships"] > 0
    g = client.get("/api/graph").json()
    assert g["nodes"] and g["edges"]
    assert any(e["label"] == "USES_METHOD" for e in g["edges"])
    a = client.post("/api/ask", json={"question": "Which methods are used for question answering?"}).json()
    assert a["citations"], "ask must return citations"
    assert a["intent"] == "methods"
    assert "does not provide enough" not in a["answer"] or a["citations"]
    gaps = client.get("/api/gaps").json()
    assert gaps and all("score" in x and "breakdown" in x and "caveat" in x for x in gaps)
    assert 0 <= gaps[0]["score"] <= 100
    topics = client.get("/api/topics").json()
    assert "topics" in topics
    docs = client.get("/api/documents").json()
    recs = client.get("/api/recommendations", params={"paper_id": docs[0]["id"]}).json()
    assert recs and "explanation" in recs[0]
    ev = client.post("/api/evaluate").json()
    assert ev["results"]

def test_duplicate_and_delete_cascade():
    docs = client.get("/api/documents").json()
    assert docs
    doc_id = docs[0]["id"]
    # Duplicate upload of same file content must be reported, not duplicated
    p = "/tmp/rm_paper0.pdf"
    with open(p, "rb") as fh:
        r = client.post("/api/documents/upload", files=[("files", ("p0.pdf", fh, "application/pdf"))]).json()
    assert r["uploaded"][0].get("duplicate_of_existing") is True
    r = client.delete(f"/api/documents/{doc_id}")
    assert r.status_code == 200
    assert not any(d["id"] == doc_id for d in client.get("/api/documents").json())
    g = client.get("/api/graph", params={"paper_id": doc_id}).json()
    assert g["edges"] == [], "deleted paper must leave no graph edges"

def test_gap_score_renormalisation():
    from app.services.gaps import score
    s, b = score({"underrepresentation": 1.0, "limitation": 0.5})
    # weights 0.30+0.25 renormalised: (0.30/0.55)*1 + (0.25/0.55)*0.5
    assert abs(s - 100 * ((0.30/0.55)*1 + (0.25/0.55)*0.5)) < 0.2
    assert abs(sum(b.values()) - 1.0) < 0.01
