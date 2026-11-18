"""Index lifecycle + BM25 / dense / hybrid (RRF) retrieval returning citation-ready evidence."""
from __future__ import annotations
import time, threading
from dataclasses import dataclass, asdict, field
from pathlib import Path
import numpy as np
from common import OUT_DIR, connect, load_config
from models.embeddings import get_embedder
from .bm25 import BM25Index
from .vector_store import VectorStore


def index_dir(owner: str = "", name: str = "") -> Path:
    return OUT_DIR / "indexes" / (owner or "shared") / (name or "default")


def rrf(rankings: list[list[str]], weights: list[float] | None = None, k: int = 60) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion: score(d) = sum_i w_i / (k + rank_i(d))."""
    weights = weights or [1.0] * len(rankings)
    sc: dict[str, float] = {}
    for w, r in zip(weights, rankings):
        for rank, cid in enumerate(r, 1):
            sc[cid] = sc.get(cid, 0.0) + w / (k + rank)
    return sorted(sc.items(), key=lambda x: -x[1])


@dataclass
class Evidence:
    doc_id: str
    chunk_id: str
    title: str | None
    section: str | None
    score: float
    passage: str
    char_start: int
    char_end: int
    metadata: dict = field(default_factory=dict)
    citation: str = ""
    scores: dict = field(default_factory=dict)   # per-stage scores (bm25 / dense / rrf / rerank)

    def to_dict(self): return asdict(self)


def build_index(owner: str = "", name: str = "", embed_key: str = "minilm", batch: int = 256, db_path=None,
                chunk_limit: int | None = None, progress=None) -> dict:
    """Incrementally embed chunks in small batches (bounded memory), then persist BM25 + FAISS."""
    con = connect(db_path)
    q = "SELECT chunk_id, text FROM chunks WHERE owner=? ORDER BY chunk_id" + (f" LIMIT {int(chunk_limit)}" if chunk_limit else "")
    rows = con.execute(q, (owner,)).fetchall()
    ids, texts = [r["chunk_id"] for r in rows], [r["text"] for r in rows]
    cfg = load_config("retrieval")
    emb = get_embedder(embed_key, max_seq_length=cfg["dense"]["max_seq_length"], batch_size=cfg["dense"]["batch_size"])
    t0 = time.perf_counter()
    bm = BM25Index(**cfg["bm25"]).build(ids, texts)
    t_bm = time.perf_counter() - t0
    vs = VectorStore(emb.dim, emb.name)
    t1 = time.perf_counter()
    for i in range(0, len(ids), batch):
        vs.add(ids[i:i + batch], emb.encode(texts[i:i + batch]))
        if progress: progress((i + batch) / max(len(ids), 1), f"embedded {min(i + batch, len(ids))}/{len(ids)}")
    t_emb = time.perf_counter() - t1
    d = index_dir(owner, name)
    bm.save(d); vs.save(d)
    return {"chunks": len(ids), "bm25_build_s": round(t_bm, 2), "embed_s": round(t_emb, 2),
            "embed_throughput_chunks_per_s": round(len(ids) / max(t_emb, 1e-9), 1),
            "index_bytes": vs.size_bytes(d), "model": emb.name, "path": str(d)}


class Retriever:
    def __init__(self, owner: str = "", name: str = "", db_path=None, embed_key: str | None = None):
        self.owner, self.db_path = owner, db_path
        d = index_dir(owner, name)
        self.bm25 = BM25Index.load(d)
        self.vs = VectorStore.load(d)
        cfg = load_config("retrieval")
        self.cfg = cfg
        key = embed_key or next((k for k, v in load_config("models")["embedding"]["candidates"].items() if v["name"] == self.vs.model_name), cfg["dense"]["model"])
        self.emb = get_embedder(key, max_seq_length=cfg["dense"]["max_seq_length"])
        self._tl = threading.local()

    @property
    def con(self):
        """Thread-local SQLite connection (retrievers are cached and shared across API worker threads)."""
        if not hasattr(self._tl, 'con'):
            self._tl.con = connect(self.db_path)
        return self._tl.con

    # ---- ranking primitives -------------------------------------------------
    def bm25_search(self, q, k=100, allowed=None): return self.bm25.search(q, k, allowed)
    def dense_search(self, q, k=100, allowed=None): return self.vs.search(self.emb.encode([q], is_query=True)[0], k, allowed)

    def hybrid_search(self, q, k=100, allowed=None, rrf_k=None, w_bm25=None, w_dense=None):
        h = self.cfg["hybrid"]
        b = self.bm25_search(q, h["candidates"], allowed); d = self.dense_search(q, h["candidates"], allowed)
        fused = rrf([[c for c, _ in b], [c for c, _ in d]], [w_bm25 or h["bm25_weight"], w_dense or h["dense_weight"]], rrf_k or h["rrf_k"])
        bs, ds = dict(b), dict(d)
        return [(c, s, {"bm25": bs.get(c), "dense": ds.get(c), "rrf": s}) for c, s in fused[:k]]

    # ---- allowed-set for access control / filters -------------------------------
    def allowed_ids(self, domains: list[str] | None = None, year_min: int | None = None, year_max: int | None = None,
                    full_text_only: bool = False, doc_ids: list[str] | None = None) -> set[str] | None:
        if not (domains or year_min or year_max or full_text_only or doc_ids):
            return None
        sql, p = "SELECT c.chunk_id FROM chunks c JOIN documents d ON d.id=c.doc_id AND d.owner=c.owner WHERE c.owner=?", [self.owner]
        if domains: sql += f" AND d.domain IN ({','.join('?'*len(domains))})"; p += domains
        if year_min: sql += " AND d.year>=?"; p.append(year_min)
        if year_max: sql += " AND d.year<=?"; p.append(year_max)
        if full_text_only: sql += " AND d.has_full_text=1"
        if doc_ids: sql += f" AND c.doc_id IN ({','.join('?'*len(doc_ids))})"; p += list(doc_ids)
        return {r[0] for r in self.con.execute(sql, p)}

    # ---- evidence assembly ------------------------------------------------------------
    def hydrate(self, ranked: list[tuple[str, float, dict]]) -> list[Evidence]:
        out = []
        for n, (cid, score, parts) in enumerate(ranked, 1):
            r = self.con.execute("SELECT c.*, d.title, d.year, d.doi, d.url, d.source, d.created, d.domain AS ddomain, d.has_full_text "
                                 "FROM chunks c JOIN documents d ON d.id=c.doc_id AND d.owner=c.owner WHERE c.chunk_id=?", (cid,)).fetchone()
            if not r: continue
            meta = {k: r[k] for k in ("year", "doi", "url", "source", "created", "has_full_text") if r[k] not in (None, "")}
            meta["domain"] = r["ddomain"]
            ev = Evidence(r["doc_id"], cid, r["title"], r["section"], score, r["text"], r["char_start"], r["char_end"], meta, "", parts)
            ev.citation = f"[{n}] {r['title'] or 'Untitled'} — {r['section'] or 'unlabeled'} — {r['text'][:160].strip()}…"
            out.append(ev)
        return out

    def search(self, q, mode="hybrid_rerank", k=10, domains=None, year_min=None, year_max=None, full_text_only=False,
               rerank_top=None, reranker=None, doc_ids=None) -> dict:
        allowed = self.allowed_ids(domains, year_min, year_max, full_text_only, doc_ids)
        lat = {}
        t = time.perf_counter()
        if mode == "bm25": ranked = [(c, s, {"bm25": s}) for c, s in self.bm25_search(q, max(k, 100), allowed)]
        elif mode == "dense": ranked = [(c, s, {"dense": s}) for c, s in self.dense_search(q, max(k, 100), allowed)]
        else: ranked = self.hybrid_search(q, max(k, 100), allowed)
        lat["retrieval_ms"] = (time.perf_counter() - t) * 1000
        if mode == "hybrid_rerank" and ranked:
            from .reranking import rerank_candidates
            t = time.perf_counter()
            ranked = rerank_candidates(self, q, ranked, rerank_top or self.cfg["rerank"]["top_k"], reranker)
            lat["rerank_ms"] = (time.perf_counter() - t) * 1000
        ev = self.hydrate(ranked[:k])
        return {"query": q, "mode": mode, "results": ev, "latency_ms": lat}


class MultiRetriever:
    """Searches several partitions (shared corpus + a user's private index) and merges by reranker score."""
    def __init__(self, retrievers: list[Retriever]):
        self.rs = retrievers
        self.cfg = retrievers[0].cfg

    @property
    def con(self): return self.rs[0].con

    def search(self, q, mode="hybrid_rerank", k=10, **kw):
        outs = [r.search(q, mode, k=k, **kw) for r in self.rs]
        ev = sorted((e for o in outs for e in o["results"]), key=lambda e: -e.score)[:k]
        lat = {key: sum(o["latency_ms"].get(key, 0) for o in outs) for key in outs[0]["latency_ms"]}
        return {"query": q, "mode": mode, "results": ev, "latency_ms": lat}
