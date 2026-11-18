"""SCIENTIA AI API. Run: uvicorn backend.main:app --port 8000"""
from __future__ import annotations
import asyncio, glob, json, os, threading
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, EmailStr

from common import OUT_DIR, connect
from backend.services import auth, jobs
from backend.services.documents import upload_and_index
from retrieval.hybrid import Retriever, MultiRetriever, index_dir, build_index
from rag.pipeline import answer_question
from rag.verification import verify_answer
from rag.citations import build_citation_table

app = FastAPI(title="SCIENTIA AI", version="0.1.0", description="Scientific Knowledge Intelligence")
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("SCIENTIA_CORS", "http://localhost:5173").split(","),
                   allow_methods=["*"], allow_headers=["*"])
TIMEOUT_S = float(os.environ.get("SCIENTIA_TIMEOUT_S", 180))
ADMINS = {e.strip().lower() for e in os.environ.get("SCIENTIA_ADMIN_EMAILS", "").split(",") if e.strip()}
_R: dict[str, Retriever] = {}
_lock = threading.Lock()


def get_retriever(owner: str = "") -> Retriever | None:
    with _lock:
        if owner not in _R:
            if not (index_dir(owner) / "faiss.index").exists(): return None
            _R[owner] = Retriever(owner)
        return _R[owner]


def retriever_for(user: str, scope: str):
    rs = []
    if scope in ("shared", "both") and (r := get_retriever("")): rs.append(r)
    if scope in ("private", "both") and (r := get_retriever(user)): rs.append(r)
    if not rs: raise HTTPException(409, "No index available for this scope. Ingest + build an index first.")
    return rs[0] if len(rs) == 1 else MultiRetriever(rs)


async def bounded(fn, *a, **kw):
    try: return await asyncio.wait_for(run_in_threadpool(fn, *a, **kw), TIMEOUT_S)
    except asyncio.TimeoutError: raise HTTPException(504, f"request exceeded {TIMEOUT_S}s")


@app.on_event("startup")
def warm():
    def go():  # lazy heavy models: warm in background so the first query is not cold
        try:
            r = get_retriever("")
            if r: r.emb.encode(["warm"]); from models.reranker import get_reranker; get_reranker().score("a", ["b"])
        except Exception: pass
    threading.Thread(target=go, daemon=True).start()


# ---------------- schemas ----------------
class Creds(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)

class Filters(BaseModel):
    domains: list[Literal["physics", "chemistry", "biology", "ai_cs", "interdisciplinary", "other"]] | None = None
    year_min: int | None = Field(None, ge=1800, le=2100)
    year_max: int | None = Field(None, ge=1800, le=2100)
    full_text_only: bool = False

class SearchReq(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    mode: Literal["bm25", "dense", "hybrid", "hybrid_rerank"] = "hybrid_rerank"
    k: int = Field(10, ge=1, le=50)
    scope: Literal["shared", "private", "both"] = "shared"
    filters: Filters = Filters()

class AskReq(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    k: int = Field(8, ge=2, le=20)
    scope: Literal["shared", "private", "both"] = "shared"
    filters: Filters = Filters()
    llm_provider: Literal["none", "openai_compatible", "ollama", "hf"] | None = None
    verify: bool = True
    paper_ids: list[str] | None = Field(None, max_length=6)   # restrict to these papers (notebook-style)

class VerifyReq(BaseModel):
    answer: str = Field(max_length=8000)
    chunk_ids: list[str] = Field(min_length=1, max_length=40)   # marker [n] == position n in this list

class IngestReq(BaseModel):
    limit: int = Field(1000, ge=10, le=1_000_000)
    shard: int = Field(0, ge=0, le=19)
    quota_per_domain: int | None = None

class IndexReq(BaseModel):
    embed_model: str = "minilm"
    shared: bool = False


# ---------------- auth ----------------
@app.post("/api/auth/register")
def register(c: Creds): uid = auth.register(c.email, c.password); auth.audit(uid, "register"); return {"user_id": uid}

@app.post("/api/auth/login")
def login(c: Creds): return {"access_token": auth.login(c.email, c.password), "token_type": "bearer"}

def require_admin(user: str = Depends(auth.current_user)) -> str:
    row = connect().execute("SELECT email FROM users WHERE id=?", (user,)).fetchone()
    if not row or row["email"] not in ADMINS: raise HTTPException(403, "admin only (set SCIENTIA_ADMIN_EMAILS)")
    return user


# ---------------- documents / ingestion / index ----------------
@app.post("/api/documents/upload", status_code=202)
async def upload(files: list[UploadFile] = File(...), user: str = Depends(auth.current_user)):
    if len(files) > 20: raise HTTPException(413, "max 20 files per request")
    payload = [(f.filename or "upload.pdf", await f.read()) for f in files]
    jid = jobs.submit(user, "upload", upload_and_index, user, payload)
    auth.audit(user, "upload", f"{len(payload)} files job={jid}")
    with _lock: _R.pop(user, None)  # reload private index after build
    return {"job_id": jid}

@app.post("/api/datasets/ingest", status_code=202)
def ingest_ds(r: IngestReq, user: str = Depends(require_admin)):
    from ingestion.pes2o_loader import ingest
    jid = jobs.submit(user, "ingest", lambda progress: ingest(r.limit, shard=r.shard, quota_per_domain=r.quota_per_domain, progress=progress)["stats"])
    auth.audit(user, "ingest", json.dumps(r.model_dump())); return {"job_id": jid}

@app.post("/api/index/build", status_code=202)
def build(r: IndexReq, user: str = Depends(auth.current_user)):
    if r.shared: require_admin(user)
    owner = "" if r.shared else user
    jid = jobs.submit(user, "index", lambda progress: build_index(owner=owner, embed_key=r.embed_model, progress=progress))
    with _lock: _R.pop(owner, None)
    auth.audit(user, "index", f"owner={owner or 'shared'}"); return {"job_id": jid}

@app.get("/api/jobs/{job_id}")
def job(job_id: str, user: str = Depends(auth.current_user)):
    j = jobs.get(job_id, user)
    if not j: raise HTTPException(404, "job not found")
    return j


# ---------------- search / ask / verify ----------------
def _flt(f: Filters): return dict(domains=f.domains, year_min=f.year_min, year_max=f.year_max, full_text_only=f.full_text_only)

@app.post("/api/search")
async def search(r: SearchReq, user: str = Depends(auth.current_user)):
    ret = retriever_for(user, r.scope)
    res = await bounded(ret.search, r.query, r.mode, r.k, **_flt(r.filters))
    auth.audit(user, "search", r.query)
    return {"query": r.query, "mode": r.mode, "latency_ms": res["latency_ms"], "results": [e.to_dict() for e in res["results"]]}

@app.post("/api/research/ask")
async def ask(r: AskReq, user: str = Depends(auth.current_user)):
    from rag.synthesis import get_llm
    from models.nli import get_nli
    ret = retriever_for(user, r.scope)
    def run(llm): return answer_question(r.question, ret, r.k, llm=llm, nli=get_nli() if r.verify else None, verify=r.verify, doc_ids=r.paper_ids, **_flt(r.filters))
    try: out = await bounded(run, get_llm(r.llm_provider))
    except HTTPException: raise
    except Exception as e:
        if r.llm_provider in (None, "none"): raise
        out = await bounded(run, get_llm("none")); out["note"] = f"The language model ({r.llm_provider}) was not reachable ({type(e).__name__}); showing the extractive answer instead."
    auth.audit(user, "ask", r.question)
    return out

@app.post("/api/research/verify")
async def verify(r: VerifyReq, user: str = Depends(auth.current_user)):
    con = connect(); cit = {}
    for n, cid in enumerate(r.chunk_ids, 1):
        row = con.execute("SELECT c.*, d.title FROM chunks c JOIN documents d ON d.id=c.doc_id AND d.owner=c.owner WHERE c.chunk_id=? AND c.owner IN ('', ?)", (cid, user)).fetchone()
        if not row: raise HTTPException(404, f"chunk not found or not accessible: {cid}")
        cit[n] = {"passage": row["text"], "title": row["title"], "section": row["section"], "chunk_id": cid}
    from models.nli import get_nli
    return await bounded(verify_answer, r.answer, cit, get_nli())


# ---------------- papers / evaluation ----------------
@app.get("/api/papers/{paper_id}")
def paper(paper_id: str, user: str = Depends(auth.current_user)):
    con = connect()
    d = con.execute("SELECT id,owner,title,text,source,added,created,version,lang,domain,doi,url,authors,year,has_full_text,meta_missing,origin FROM documents WHERE id=? AND owner IN ('', ?) ORDER BY owner DESC", (paper_id, user)).fetchone()
    if not d: raise HTTPException(404, "paper not found")
    ch = [dict(r) for r in con.execute("SELECT chunk_id,idx,section,char_start,char_end,n_tokens FROM chunks WHERE doc_id=? AND owner=? ORDER BY idx", (paper_id, d["owner"]))]
    out = dict(d); out["abstract_or_text_preview"] = out.pop("text")[:3000]; out["chunks"] = ch
    out["metadata_note"] = "Only fields present in the source record are shown; missing: " + (d["meta_missing"] or "none")
    return out

@app.get("/api/evaluation/results")
def eval_results(user: str = Depends(auth.current_user)):
    return {Path(p).stem: json.load(open(p)) for p in sorted(glob.glob(str(OUT_DIR / "evaluations" / "*.json")))}


# ---------------- not yet implemented: explicit 501, never fake data ----------------
def _ni(name): raise HTTPException(501, f"{name} is not implemented yet in this build (see README roadmap).")
class ExtractReq(BaseModel):
    paper_id: str = Field(min_length=1, max_length=128)
    method: Literal["rules", "llm"] = "rules"
    force: bool = False


def _owner_of(paper_id: str, user: str) -> str:
    """Resolve which partition holds a paper the caller may access (own private copy wins, else shared). 404 otherwise."""
    row = connect().execute("SELECT owner FROM documents WHERE id=? AND owner IN ('', ?) ORDER BY owner DESC", (paper_id, user)).fetchone()
    if not row: raise HTTPException(404, "paper not found")
    return row["owner"]


@app.post("/api/research/extract")
async def extract(r: ExtractReq, user: str = Depends(auth.current_user)):
    from extraction.findings import extract_paper
    from rag.synthesis import get_llm
    owner = _owner_of(r.paper_id, user)
    llm = get_llm("openai_compatible") if r.method == "llm" else None
    try:
        out = await bounded(extract_paper, r.paper_id, owner, llm, None, r.force)
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(502 if r.method == "llm" else 500, f"extraction failed: {type(e).__name__}: {e}")
    auth.audit(user, "extract", f"{r.paper_id} {r.method}")
    return out


class CompareReq(BaseModel):
    paper_ids: list[str] = Field(min_length=2, max_length=6)
    method: Literal["rules", "llm"] = "rules"
    detect_tensions: bool = False

@app.post("/api/research/compare")
async def compare(r: CompareReq, user: str = Depends(auth.current_user)):
    from extraction.findings import extract_paper
    from extraction.compare import compare as run_compare
    from rag.synthesis import get_llm
    ids = list(dict.fromkeys(r.paper_ids))
    if len(ids) < 2: raise HTTPException(422, "provide at least two distinct paper ids")
    owners = {i: _owner_of(i, user) for i in ids}
    llm = get_llm("openai_compatible") if r.method == "llm" else None
    def work():
        ex = {i: extract_paper(i, owners[i], llm)["extraction"] for i in ids}
        titles = {i: (connect().execute("SELECT title FROM documents WHERE id=? AND owner=?", (i, owners[i])).fetchone() or {"title": None})["title"] for i in ids}
        nli = None
        if r.detect_tensions:
            from models.nli import get_nli
            nli = get_nli()
        return run_compare(ex, titles, nli)
    try: out = await bounded(work)
    except HTTPException: raise
    except Exception as e: raise HTTPException(502 if r.method == "llm" else 500, f"comparison failed: {type(e).__name__}: {e}")
    auth.audit(user, "compare", ",".join(ids))
    return out

class StudioReq(BaseModel):
    paper_ids: list[str] = Field(min_length=1, max_length=6)
    kind: Literal["overview", "mindmap", "slides", "audio", "video"]
    fluent: bool = False   # audio/video only: local-LLM narration, checked against the source
    ai_design: bool = False   # slides only: Claude/OpenAI designs theme, layouts, headlines, notes (sends extracted text to that provider)

@app.post("/api/studio/generate", status_code=202)
def studio_generate(r: StudioReq, user: str = Depends(auth.current_user)):
    from studio.service import generate
    ids = list(dict.fromkeys(r.paper_ids))
    owners = {i: _owner_of(i, user) for i in ids}
    jid = jobs.submit(user, f"studio:{r.kind}", generate, user, ids, owners, r.kind, max_retries=0, fluent=r.fluent, ai_design=r.ai_design)
    auth.audit(user, "studio", f"{r.kind} {','.join(ids)} job={jid}")
    return {"job_id": jid}

@app.get("/api/studio/file/{key}/{name}")
def studio_file(key: str, name: str, user: str = Depends(auth.current_user)):
    import re
    from fastapi.responses import FileResponse
    from studio.service import user_dir
    if not re.fullmatch(r"[0-9a-f]{12}", key) or not re.fullmatch(r"overview\.m4a|overview\.mp4|slides\.pdf|deck\.pptx|slide_\d\d\.png", name): raise HTTPException(404, "not found")
    p = user_dir(user) / key / name
    if not p.is_file(): raise HTTPException(404, "not found")
    return FileResponse(p, media_type={"m4a": "audio/mp4", "mp4": "video/mp4", "pdf": "application/pdf", "png": "image/png", "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}[name.rsplit(".", 1)[1]])


_G: dict = {}


def get_graph_for(owner: str):
    """Shared graph is built offline (scripts/build_graph.py). A user's private graph is built on demand from rule extraction."""
    from knowledge_graph.graph_builder import load_graph, build_graph, save_graph
    from extraction.findings import extract_paper
    with _lock:
        if owner in _G: return _G[owner]
        g = load_graph(owner)
        if g is None and owner:
            for d in connect().execute("SELECT id FROM documents WHERE owner=?", (owner,)).fetchall():
                extract_paper(d["id"], owner)
            g = build_graph(owner, with_similarity=False); save_graph(g, owner)
        if g is not None: _G[owner] = g
        return g


def _resolve_graph(paper_id: str | None, user: str):
    from knowledge_graph.graph_builder import pid
    if paper_id:
        owner = _owner_of(paper_id, user)
        g = get_graph_for(owner)
        if g is None or pid(paper_id) not in g: raise HTTPException(404, "paper has no graph yet (run extraction + scripts/build_graph.py)")
        return g
    g = get_graph_for("")
    if g is None: raise HTTPException(409, "No graph built. Run scripts/run_extraction.py then scripts/build_graph.py.")
    return g


@app.get("/api/graph/search/entities")
def graph_search(q: str, type: str | None = None, user: str = Depends(auth.current_user)):
    from knowledge_graph import graph_queries as gq
    if len(q) < 2: raise HTTPException(422, "q too short")
    return {"results": gq.search_entities(_resolve_graph(None, user), q, 20, type)}


@app.get("/api/graph/summary/overview")
def graph_overview(user: str = Depends(auth.current_user)):
    from knowledge_graph import graph_queries as gq
    g = _resolve_graph(None, user)
    cl = [{k: v for k, v in c.items() if k != "members"} for c in gq.clusters(g)[:10]]
    return {"stats": g.graph.get("stats"), "clusters": cl,
            "note": "citation edges are only present when verified bibliographic metadata was loaded; semantic edges are embedding similarity, not citations"}


@app.get("/api/graph/{paper_id}")
def graph(paper_id: str, mode: Literal["concept", "paper", "evidence"] = "concept", max_nodes: int = 60,
          domains: str | None = None, rels: str | None = None, user: str = Depends(auth.current_user)):
    from knowledge_graph import graph_queries as gq
    g = _resolve_graph(paper_id, user)
    max_nodes = max(5, min(max_nodes, 200))      # never render unbounded graphs
    sub = gq.subgraph(g, mode, paper_id, max_nodes, domains.split(",") if domains else None, rels.split(",") if rels else None)
    out = {**sub, "related": gq.related_papers(g, paper_id, 8)}
    return out


@app.post("/api/models/train")
def train(user: str = Depends(require_admin)): _ni("training API (use scripts under training/)")

@app.get("/api/health")
def health(): return {"ok": True, "shared_index": (index_dir("") / "faiss.index").exists()}
