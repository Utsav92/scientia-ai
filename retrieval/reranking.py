from __future__ import annotations
from models.reranker import get_reranker


def rerank_candidates(retriever, query: str, ranked: list, top_k: int = 30, reranker=None):
    """Re-score the top_k fused candidates with a cross-encoder; remaining candidates keep fused order below them."""
    reranker = reranker or get_reranker(retriever.cfg["rerank"]["model"])
    head, tail = ranked[:top_k], ranked[top_k:]
    texts = []
    for cid, _, _ in head:
        r = retriever.con.execute("SELECT text FROM chunks WHERE chunk_id=?", (cid,)).fetchone()
        texts.append(r["text"] if r else "")
    sc = reranker.score(query, texts)
    order = sorted(range(len(head)), key=lambda i: -sc[i])
    new = [(head[i][0], float(sc[i]), {**head[i][2], "rerank": float(sc[i])}) for i in order]
    floor = min([s for _, s, _ in new], default=0.0) - 1.0
    return new + [(c, floor - j * 1e-6, p) for j, (c, _, p) in enumerate(tail)]
