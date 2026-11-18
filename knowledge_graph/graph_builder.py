"""Knowledge graph (NetworkX MultiDiGraph) built ONLY from stored extractions + real metadata.

Edge `kind` separates provenance classes so they are never conflated in the UI:
  extracted : derived from a verbatim span of a paper (carries `quote`)
  semantic  : embedding similarity between papers (carries `score`) - NOT a citation
  citation  : verified bibliographic link supplied via add_citations(); the corpus has none today
"""
from __future__ import annotations
import json, pickle, re
from pathlib import Path
import numpy as np
import networkx as nx
from common import connect, OUT_DIR
from extraction.relations import extract_relations

REL_BY_TYPE = {"METHOD": "USES_METHOD", "MODEL": "USES_METHOD", "ALGORITHM": "USES_METHOD", "DATASET": "EVALUATED_ON", "METRIC": "REPORTS_METRIC",
               "MATERIAL": "STUDIES", "CHEMICAL": "STUDIES", "BIOLOGICAL_ENTITY": "STUDIES", "BIOLOGICAL_DATA": "STUDIES"}
SKIP_TYPES = {"PHYSICAL_QUANTITY", "EXPERIMENTAL_CONDITION", "TASK"}   # too noisy as graph nodes at baseline quality


def pid(i): return f"paper:{i}"
def eid(t, c): return f"ent:{t}:{c}"


def graph_path(owner: str = "") -> Path:
    return OUT_DIR / "graph" / f"{owner or 'shared'}.pkl"


def _snippet(text: str, a: int | None, b: int | None, pad=60) -> str:
    if a is None: return ""
    s = text[max(0, a - pad):min(len(text), b + pad)].replace("\n", " ")
    return s.strip()


def build_graph(owner: str = "", method: str = "rules", with_relations=True, with_similarity=True, sim_k=5, sim_min=0.55,
                db_path=None, retriever=None) -> nx.MultiDiGraph:
    con = connect(db_path)
    g = nx.MultiDiGraph()
    docs = {r["id"]: dict(r) for r in con.execute("SELECT id,title,domain,year,text FROM documents WHERE owner=?", (owner,))}
    ex_rows = con.execute("SELECT doc_id,data,method FROM extractions WHERE owner=? AND method LIKE ?", (owner, method + "%")).fetchall()
    # prefer one extraction per doc: llm over rules when both are requested via method='' (handled by caller); here take what matches
    for r in ex_rows:
        d = docs.get(r["doc_id"])
        if not d: continue
        ex = json.loads(r["data"])
        p = pid(r["doc_id"])
        g.add_node(p, kind="paper", label=(d["title"] or "Untitled")[:120], domain=d["domain"], year=d["year"], doc_id=r["doc_id"])
        for e in ex["entities"]:
            if e["type"] in SKIP_TYPES: continue
            n = eid(e["type"], e["canonical"])
            if n not in g: g.add_node(n, kind="entity", etype=e["type"], label=e["canonical"])
            if not g.has_edge(p, n):
                g.add_edge(p, n, rel=REL_BY_TYPE.get(e["type"], "MENTIONS"), kind="extracted", quote=_snippet(d["text"], e["char_start"], e["char_end"]))
        for key, rel in (("findings", "REPORTS_FINDING"), ("quantitative_results", "REPORTS_FINDING"), ("limitations", "HAS_LIMITATION")):
            for i, f in enumerate(ex[key]):
                fid = f"finding:{r['doc_id']}:{key[0]}{i}"
                g.add_node(fid, kind="finding" if rel == "REPORTS_FINDING" else "limitation", label=f["text"][:140], doc_id=r["doc_id"], quote=f["quote"], chunk_ids=f["chunk_ids"])
                g.add_edge(p, fid, rel=rel, kind="extracted", quote=f["quote"], chunk_ids=f["chunk_ids"])
        if with_relations:
            for rel in extract_relations(d["text"]):
                a, b = eid(rel["head_type"], rel["head"]), eid(rel["tail_type"], rel["tail"])
                for n, t, c in ((a, rel["head_type"], rel["head"]), (b, rel["tail_type"], rel["tail"])):
                    if n not in g: g.add_node(n, kind="entity", etype=t, label=c)
                if not any(dd.get("rel") == rel["rel"] and dd.get("doc_id") == r["doc_id"] for dd in (g.get_edge_data(a, b) or {}).values()):
                    g.add_edge(a, b, rel=rel["rel"], kind="extracted", quote=rel["evidence"], doc_id=r["doc_id"])
    if with_similarity and retriever is not None:
        _add_similarity(g, retriever, sim_k, sim_min)
    g.graph["stats"] = graph_stats(g)
    return g


def _add_similarity(g, retriever, k, thr):
    """Paper-paper edges from mean chunk embeddings. Labelled `semantic`; never presented as citation."""
    vs = retriever.vs
    X = np.vstack([vs.index.reconstruct(i) for i in range(vs.index.ntotal)]) if vs.index.ntotal else np.zeros((0, vs.dim), "float32")
    by_doc: dict[str, list[int]] = {}
    for i, cid in enumerate(vs.ids):
        by_doc.setdefault(cid.rsplit(":", 1)[0].split("/")[-1], []).append(i)
    keep = [d for d in by_doc if pid(d) in g]
    if len(keep) < 2: return
    M = np.vstack([X[by_doc[d]].mean(0) for d in keep]); M /= np.linalg.norm(M, axis=1, keepdims=True) + 1e-9
    for s in range(0, len(keep), 1024):
        S = M[s:s + 1024] @ M.T
        for r in range(S.shape[0]):
            S[r, s + r] = -1
            for j in np.argpartition(-S[r], min(k, S.shape[1] - 1))[:k]:
                if S[r, j] >= thr:
                    g.add_edge(pid(keep[s + r]), pid(keep[j]), rel="SIMILAR_TO", kind="semantic", score=float(S[r, j]))


def add_citations(g: nx.MultiDiGraph, pairs: list[tuple[str, str]], source: str):
    """Add VERIFIED citation edges (citing_doc_id, cited_doc_id) from real bibliographic metadata. Unknown ids are rejected."""
    n = 0
    for a, b in pairs:
        if pid(a) in g and pid(b) in g:
            g.add_edge(pid(a), pid(b), rel="CITES", kind="citation", source=source); n += 1
    g.graph["stats"] = graph_stats(g)
    return n


def graph_stats(g) -> dict:
    kinds, rels, nk = {}, {}, {}
    for _, _, d in g.edges(data=True):
        kinds[d.get("kind")] = kinds.get(d.get("kind"), 0) + 1; rels[d.get("rel")] = rels.get(d.get("rel"), 0) + 1
    for _, d in g.nodes(data=True): nk[d.get("kind")] = nk.get(d.get("kind"), 0) + 1
    return {"nodes": g.number_of_nodes(), "edges": g.number_of_edges(), "node_kinds": nk, "edge_kinds": kinds, "relations": rels,
            "citation_edges": kinds.get("citation", 0)}


def save_graph(g, owner=""):
    p = graph_path(owner); p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as f: pickle.dump(g, f)


def load_graph(owner="") -> nx.MultiDiGraph | None:
    p = graph_path(owner)
    return pickle.load(open(p, "rb")) if p.exists() else None
