"""Retrieval evaluation on BEIR datasets (default: SciFact) with measured latency.

Self-contained metrics (Recall@k, MRR@10, nDCG@10, P@5). Fusion params are tuned on a DEV split of the
queries only; reported numbers are on the held-out TEST split. BEIR's own test qrels are used for test;
dev is carved from the train qrels, so there is no leakage from test labels into tuning.
"""
from __future__ import annotations
import json, math, time, io, zipfile, itertools
from pathlib import Path
import numpy as np, httpx
from common import OUT_DIR
from models.embeddings import Embedder
from models.reranker import CrossEncoderReranker
from retrieval.bm25 import BM25Index
from retrieval.vector_store import VectorStore
from retrieval.hybrid import rrf

BEIR_URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/{}.zip"


def load_beir(name="scifact", cache=OUT_DIR / "beir"):
    d = cache / name
    if not d.exists():
        cache.mkdir(parents=True, exist_ok=True)
        r = httpx.get(BEIR_URL.format(name), follow_redirects=True, timeout=300); r.raise_for_status()
        zipfile.ZipFile(io.BytesIO(r.content)).extractall(cache)
    corpus = {}
    for l in open(d / "corpus.jsonl"):
        j = json.loads(l); corpus[j["_id"]] = ((j.get("title") or "") + ". " + j["text"]).strip(". ")
    queries = {json.loads(l)["_id"]: json.loads(l)["text"] for l in open(d / "queries.jsonl")}
    def qrels(split):
        out, p = {}, d / "qrels" / f"{split}.tsv"
        if not p.exists(): return out
        for l in list(open(p))[1:]:
            q, c, s = l.strip().split("\t")
            if int(s) > 0: out.setdefault(q, {})[c] = int(s)
        return out
    return corpus, queries, qrels("train"), qrels("test")


def metrics(ranked: dict[str, list[str]], qrels: dict[str, dict[str, int]]) -> dict:
    ks = (1, 5, 10, 100)
    R = {f"recall@{k}": [] for k in ks}; mrr, ndcg, p5 = [], [], []
    for q, rel in qrels.items():
        r = ranked.get(q, [])
        for k in ks: R[f"recall@{k}"].append(len(set(r[:k]) & set(rel)) / len(rel))
        mrr.append(next((1 / (i + 1) for i, c in enumerate(r[:10]) if c in rel), 0.0))
        p5.append(sum(c in rel for c in r[:5]) / 5)
        dcg = sum(rel.get(c, 0) / math.log2(i + 2) for i, c in enumerate(r[:10]))
        idcg = sum(g / math.log2(i + 2) for i, g in enumerate(sorted(rel.values(), reverse=True)[:10]))
        ndcg.append(dcg / idcg if idcg else 0.0)
    out = {k: float(np.mean(v)) for k, v in R.items()}
    out.update({"mrr@10": float(np.mean(mrr)), "ndcg@10": float(np.mean(ndcg)), "precision@5": float(np.mean(p5)), "n_queries": len(qrels)})
    return out


def run(dataset="scifact", embed_key="minilm", rerank_top=50, max_dev=150):
    corpus, queries, train_q, test_q = load_beir(dataset)
    ids = list(corpus); texts = [corpus[i] for i in ids]
    emb = Embedder(embed_key); ce = CrossEncoderReranker()
    bm = BM25Index().build(ids, texts)
    t = time.perf_counter(); vs = VectorStore(emb.dim, emb.name); vs.add(ids, emb.encode(texts)); embed_s = time.perf_counter() - t
    dev_q = dict(itertools.islice(train_q.items(), max_dev))

    def cands(qs):
        out = {}
        for q in qs:
            b = bm.search(queries[q], 100); d = vs.search(emb.encode([queries[q]], is_query=True)[0], 100)
            out[q] = (b, d)
        return out
    dev_c, test_c = cands(dev_q), cands(test_q)
    # tune RRF on DEV only
    grid = [(k, wb) for k in (10, 30, 60, 100) for wb in (0.5, 1.0, 1.5)]
    best, best_s = None, -1
    for k, wb in grid:
        rk = {q: [c for c, _ in rrf([[c for c, _ in b], [c for c, _ in d]], [wb, 1.0], k)][:100] for q, (b, d) in dev_c.items()}
        s = metrics(rk, dev_q)["ndcg@10"]
        if s > best_s: best, best_s = (k, wb), s
    k, wb = best
    res, lat = {}, {}
    rankings = {
        "bm25": {q: [c for c, _ in b] for q, (b, d) in test_c.items()},
        "dense": {q: [c for c, _ in d] for q, (b, d) in test_c.items()},
        "hybrid": {q: [c for c, _ in rrf([[c for c, _ in b], [c for c, _ in d]], [wb, 1.0], k)][:100] for q, (b, d) in test_c.items()},
    }
    t = time.perf_counter(); rr = {}
    for q, hyb in rankings["hybrid"].items():
        head = hyb[:rerank_top]; sc = ce.score(queries[q], [corpus[c] for c in head])
        rr[q] = [head[i] for i in np.argsort(-sc)] + hyb[rerank_top:]
    lat["rerank_ms_per_query"] = (time.perf_counter() - t) * 1000 / len(test_q)
    rankings["hybrid+rerank"] = rr
    for n, r in rankings.items(): res[n] = metrics(r, test_q)
    out = {"dataset": dataset, "embedding": emb.name, "reranker": ce.name, "corpus_size": len(corpus),
           "fusion_params_tuned_on_dev": {"rrf_k": k, "bm25_weight": wb, "dev_queries": len(dev_q), "dev_ndcg@10": best_s},
           "test_results": res, "latency": lat, "embed_corpus_s": round(embed_s, 1),
           "embed_docs_per_s": round(len(ids) / embed_s, 1), "rerank_top": rerank_top}
    (OUT_DIR / "evaluations").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "evaluations" / f"retrieval_{dataset}_{embed_key}.json").write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    import sys
    o = run(*(sys.argv[1:2] or ["scifact"]))
    print(json.dumps(o, indent=2))
