from __future__ import annotations
import math
from collections import Counter
import networkx as nx
from .graph_builder import pid


def _papers(g): return [n for n, d in g.nodes(data=True) if d.get("kind") == "paper"]


def _ents_of(g, p) -> set[str]:
    return {v for _, v, d in g.out_edges(p, data=True) if g.nodes[v].get("kind") == "entity" and d.get("kind") == "extracted"}


def _papers_of(g, e) -> set[str]:
    return {u for u, _, d in g.in_edges(e, data=True) if g.nodes[u].get("kind") == "paper"}


def search_entities(g, q: str, limit=20, etype: str | None = None):
    q = q.lower().strip()
    out = [(n, d) for n, d in g.nodes(data=True) if d.get("kind") == "entity" and q in d["label"].lower() and (not etype or d["etype"] == etype)]
    out.sort(key=lambda x: (-len(_papers_of(g, x[0])), len(x[1]["label"])))
    return [{"id": n, "label": d["label"], "type": d["etype"], "n_papers": len(_papers_of(g, n))} for n, d in out[:limit]]


def related_papers(g, paper_id: str, k=10):
    """Rank by shared extracted entities, IDF-weighted (rare shared entities matter more). Evidence = the shared entities.
    Semantic neighbours are returned separately and labelled as such."""
    p = pid(paper_id)
    if p not in g: raise KeyError(paper_id)
    N = max(len(_papers(g)), 1)
    mine = _ents_of(g, p); scores: Counter = Counter(); why: dict[str, list] = {}
    for e in mine:
        ps = _papers_of(g, e)
        w = math.log((N + 1) / (len(ps) + 1))
        for o in ps - {p}:
            scores[o] += w; why.setdefault(o, []).append(g.nodes[e]["label"])
    shared = [{"paper_id": g.nodes[o]["doc_id"], "title": g.nodes[o]["label"], "score": round(s, 3), "shared_entities": why[o], "kind": "shared_entity"} for o, s in scores.most_common(k)]
    sem = sorted([(v, d["score"]) for _, v, d in g.out_edges(p, data=True) if d.get("kind") == "semantic"], key=lambda x: -x[1])[:k]
    semantic = [{"paper_id": g.nodes[v]["doc_id"], "title": g.nodes[v]["label"], "score": round(s, 3), "kind": "semantic_similarity"} for v, s in sem]
    cites = [{"paper_id": g.nodes[v]["doc_id"], "title": g.nodes[v]["label"], "kind": "citation"} for _, v, d in g.out_edges(p, data=True) if d.get("kind") == "citation"]
    return {"shared_entity": shared, "semantic_similarity": semantic, "citations": cites}


def common_methods(g, paper_ids: list[str]):
    sets = [{e for e in _ents_of(g, pid(i)) if g.nodes[e]["etype"] in ("METHOD", "MODEL", "ALGORITHM")} for i in paper_ids if pid(i) in g]
    if not sets: return []
    common = set.intersection(*sets)
    return sorted(g.nodes[e]["label"] for e in common)


def connected_topics(g, entity_id: str, k=15):
    """Entities that co-occur with `entity_id` in the same papers (count of shared papers)."""
    c: Counter = Counter()
    for p in _papers_of(g, entity_id):
        for e in _ents_of(g, p) - {entity_id}: c[e] += 1
    return [{"id": e, "label": g.nodes[e]["label"], "type": g.nodes[e]["etype"], "shared_papers": n} for e, n in c.most_common(k)]


def clusters(g, min_papers=2, max_entities=400, seed=1):
    """Entity communities from the co-occurrence projection (greedy modularity). Returns labelled clusters."""
    ents = [n for n, d in g.nodes(data=True) if d.get("kind") == "entity" and len(_papers_of(g, n)) >= min_papers]
    ents = sorted(ents, key=lambda e: -len(_papers_of(g, e)))[:max_entities]
    H = nx.Graph(); H.add_nodes_from(ents); es = set(ents)
    for p in _papers(g):
        pe = sorted(_ents_of(g, p) & es)
        for i in range(len(pe)):
            for j in range(i + 1, len(pe)):
                w = H.get_edge_data(pe[i], pe[j], {}).get("weight", 0) + 1; H.add_edge(pe[i], pe[j], weight=w)
    H.remove_nodes_from([n for n in list(H) if H.degree(n) == 0])
    if H.number_of_nodes() < 2: return []
    comms = nx.algorithms.community.greedy_modularity_communities(H, weight="weight")
    out = []
    for i, cm in enumerate(sorted(comms, key=len, reverse=True)):
        top = sorted(cm, key=lambda e: -len(_papers_of(g, e)))[:6]
        out.append({"cluster": i, "size": len(cm), "top_entities": [g.nodes[e]["label"] for e in top], "members": list(cm)})
    return out


def trace_evidence(g, finding_id: str):
    d = g.nodes[finding_id]
    return {"finding": d["label"], "quote": d.get("quote"), "chunk_ids": d.get("chunk_ids", []), "doc_id": d.get("doc_id"),
            "kind": d["kind"]}


def subgraph(g, mode: str, center: str | None = None, max_nodes=60, domains: list[str] | None = None, rels: list[str] | None = None) -> dict:
    """Bounded subgraph for the UI. mode: concept | paper | evidence. `center` = paper doc_id or entity node id."""
    keep: list[str] = []
    cp = pid(center) if center and pid(center) in g else None
    if mode == "evidence":
        if cp is None: return {"nodes": [], "edges": [], "note": "evidence mode needs a paper id"}
        keep = [cp] + [v for _, v, d in g.out_edges(cp, data=True) if g.nodes[v].get("kind") in ("finding", "limitation")]
    elif mode == "paper":
        if cp is None:
            keep = sorted(_papers(g), key=lambda p: -g.degree(p))[:max_nodes]
        else:
            rp = related_papers(g, center, k=max_nodes)
            keep = [cp] + [pid(x["paper_id"]) for x in rp["shared_entity"] + rp["semantic_similarity"] + rp["citations"]]
    else:  # concept
        if center and center in g:
            keep = [center] + [x["id"] for x in connected_topics(g, center, max_nodes)]
        elif cp is not None:
            ents = sorted(_ents_of(g, cp), key=lambda e: -len(_papers_of(g, e)))
            keep = [cp] + ents[:max_nodes]
        else:
            keep = sorted([n for n, d in g.nodes(data=True) if d.get("kind") == "entity"], key=lambda e: -len(_papers_of(g, e)))[:max_nodes]
    keep = list(dict.fromkeys(keep))[:max_nodes]
    if domains:
        keep = [n for n in keep if g.nodes[n].get("kind") != "paper" or g.nodes[n].get("domain") in domains]
    ks = set(keep)
    nodes = [{"id": n, **{k: v for k, v in g.nodes[n].items() if k in ("kind", "label", "domain", "year", "etype", "doc_id", "quote", "chunk_ids")}} for n in keep]
    edges, seen = [], set()
    for u, v, d in g.edges(data=True):
        if u in ks and v in ks and (not rels or d["rel"] in rels):
            key = (u, v, d["rel"])
            if key in seen: continue
            seen.add(key)
            edges.append({"source": u, "target": v, "rel": d["rel"], "kind": d["kind"], **{k: d[k] for k in ("quote", "score", "chunk_ids", "source") if k in d}})
    # concept mode between entities: add co-occurrence edges (explicitly typed as derived)
    return {"nodes": nodes, "edges": edges, "truncated": len(keep) >= max_nodes, "mode": mode}
