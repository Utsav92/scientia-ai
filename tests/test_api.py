import io, os, pytest, pymupdf
from fastapi.testclient import TestClient

PAPER = ("Chiral Perovskite Photodetectors\n\nAbstract\nWe demonstrate circularly polarized light detection using chiral perovskite films. "
         "The photodetector achieves a dissymmetry factor of 0.35 under 450 nm illumination. Devices were fabricated by spin coating.\n\n"
         "Results\nThe responsivity reached 12 mA/W at zero bias. Stability exceeded 500 hours in ambient conditions. " * 3)


def make_pdf(text):
    d = pymupdf.open(); 
    for chunk in [text[i:i + 1800] for i in range(0, len(text), 1800)]:
        p = d.new_page(); p.insert_textbox(pymupdf.Rect(40, 40, 550, 800), chunk, fontsize=10)
    return d.tobytes()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SCIENTIA_DB", str(tmp_path / "t.db")); monkeypatch.setenv("SCIENTIA_OUT_DIR", str(tmp_path / "out"))
    import importlib, common
    importlib.reload(common)
    import retrieval.hybrid as h, backend.services.auth as a, backend.services.jobs as j, backend.services.documents as dd, backend.main as m
    for mod in (h, a, j, dd, m): importlib.reload(mod)
    return TestClient(m.app)


def reg(c, email):
    c.post("/api/auth/register", json={"email": email, "password": "correct-horse-1"})
    t = c.post("/api/auth/login", json={"email": email, "password": "correct-horse-1"}).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}


def test_auth_required(client):
    assert client.post("/api/search", json={"query": "x y"}).status_code == 401
    assert client.get("/api/papers/1").status_code == 401


def test_not_implemented_is_501_not_fake(client):
    h = reg(client, "a@x.org")
    assert client.post("/api/research/compare", headers=h).status_code == 422   # implemented now: needs a valid body
    assert client.post("/api/research/compare", headers=h, json={"paper_ids": ["nope", "nada"]}).status_code == 404
    assert client.post("/api/models/train", headers=h).status_code in (401, 403, 501)


def test_upload_index_search_and_isolation(client):
    import time
    ha, hb = reg(client, "alice@x.org"), reg(client, "bob@x.org")
    r = client.post("/api/documents/upload", headers=ha, files=[("files", ("p.pdf", make_pdf(PAPER), "application/pdf"))])
    assert r.status_code == 202
    jid = r.json()["job_id"]
    for _ in range(120):
        j = client.get(f"/api/jobs/{jid}", headers=ha).json()
        if j["status"] in ("done", "failed"): break
        time.sleep(1)
    assert j["status"] == "done", j
    assert j["result"]["files"][0]["chunks"] >= 1
    # job is private to its owner
    assert client.get(f"/api/jobs/{jid}", headers=hb).status_code == 404
    # alice can search her private doc; bob has no private index
    s = client.post("/api/search", headers=ha, json={"query": "circularly polarized light detection perovskite", "scope": "private", "mode": "hybrid", "k": 3})
    assert s.status_code == 200 and "Perovskite" in s.json()["results"][0]["title"]
    assert client.post("/api/search", headers=hb, json={"query": "perovskite", "scope": "private"}).status_code == 409
    a = client.post("/api/research/ask", headers=ha, json={"question": "What responsivity did the chiral perovskite photodetector reach?", "scope": "private", "k": 3, "filters": {"full_text_only": True}})
    assert a.status_code == 200, a.text
    body = a.json()
    assert body["citations"] and "answer" in body
    assert all(c["doi"] is None or c["doi"].startswith("10.") for c in body["citations"].values())
    pid = s.json()["results"][0]["doc_id"]
    assert client.get(f"/api/papers/{pid}", headers=ha).status_code == 200
    assert client.get(f"/api/papers/{pid}", headers=hb).status_code == 404   # cross-user access denied
    # verify endpoint refuses another user's chunk
    cid = s.json()["results"][0]["chunk_id"]
    assert client.post("/api/research/verify", headers=hb, json={"answer": "x [1].", "chunk_ids": [cid]}).status_code == 404


def test_extract_and_graph_endpoints_and_isolation(client):
    import time
    ha, hb = reg(client, "alice2@x.org"), reg(client, "bob2@x.org")
    r = client.post("/api/documents/upload", headers=ha, files=[("files", ("p.pdf", make_pdf(PAPER), "application/pdf"))])
    jid = r.json()["job_id"]
    for _ in range(120):
        j = client.get(f"/api/jobs/{jid}", headers=ha).json()
        if j["status"] in ("done", "failed"): break
        time.sleep(1)
    assert j["status"] == "done", j
    pid_ = j["result"]["files"][0]["doc_id"]
    e = client.post("/api/research/extract", headers=ha, json={"paper_id": pid_})
    assert e.status_code == 200 and e.json()["extraction"]["paper_id"] == pid_
    g = client.get(f"/api/graph/{pid_}?mode=concept&max_nodes=10", headers=ha)
    assert g.status_code == 200 and len(g.json()["nodes"]) <= 10 and g.json()["related"]["citations"] == []
    assert client.get(f"/api/graph/{pid_}/", headers=hb).status_code in (404, 307)
    assert client.get(f"/api/graph/{pid_}", headers=hb).status_code == 404            # other user's paper
    assert client.post("/api/research/extract", headers=hb, json={"paper_id": pid_}).status_code == 404
    assert client.post("/api/research/extract", headers=ha, json={"paper_id": "nope"}).status_code == 404
    # comparison: isolation, validation, and a real two-paper result
    r2 = client.post("/api/documents/upload", headers=ha, files=[("files", ("q.pdf", make_pdf(PAPER.replace("Chiral", "Achiral").replace("0.35", "0.10")), "application/pdf"))])
    for _ in range(120):
        j2 = client.get(f"/api/jobs/{r2.json()['job_id']}", headers=ha).json()
        if j2["status"] in ("done", "failed"): break
        time.sleep(1)
    pid2 = j2["result"]["files"][0]["doc_id"]
    assert client.post("/api/research/compare", headers=hb, json={"paper_ids": [pid_, pid2]}).status_code == 404   # other user's papers
    assert client.post("/api/research/compare", headers=ha, json={"paper_ids": [pid_, pid_]}).status_code == 422   # needs two distinct
    c = client.post("/api/research/compare", headers=ha, json={"paper_ids": [pid_, pid2]})
    assert c.status_code == 200, c.text
    body = c.json()
    assert [p["paper_id"] for p in body["papers"]] == [pid_, pid2] and body["tensions"] is None
    assert set(body["dimensions"]) >= {"findings", "methodology", "limitations"}


def test_login_survives_server_restart(client):
    import importlib, backend.services.auth as a
    h = reg(client, "restart@x.org")
    assert client.get("/api/jobs/none", headers=h).status_code in (404, 200)       # token valid before
    importlib.reload(a)                                                            # simulates a process restart (same OUT_DIR)
    import backend.main as m; importlib.reload(m)
    from fastapi.testclient import TestClient
    assert TestClient(m.app).get("/api/jobs/none", headers=h).status_code != 401   # same token still accepted
