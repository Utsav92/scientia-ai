"""Calibrate / evaluate the RAG abstention threshold (ABSTAIN_RERANK_MIN) on BEIR SciFact.

Protocol (gold-removal): for each query we score two situations with the SAME retriever + reranker:
  * answerable   - full corpus; the query's gold documents are present.
  * unanswerable - that query's gold documents are removed from the candidate pool, so the corpus
                   contains no document the annotators judged relevant (near-miss topical docs remain,
                   which is the hard, realistic case).
The abstention signal is the max cross-encoder logit over the evidence the pipeline would use (top-k after rerank).
Threshold is chosen on DEV queries only (carved from train qrels); metrics are reported on the held-out TEST queries.

Caveats (also written into the output JSON): SciFact qrels are incomplete, so some "unanswerable" variants still
contain an unlabelled relevant doc (this makes the measured abstention rate a LOWER bound); queries are claims,
not natural questions; ms-marco logits are not probabilities.
"""
from __future__ import annotations
import json, itertools
import numpy as np
from common import OUT_DIR
from evaluation.retrieval_eval import load_beir
from models.embeddings import Embedder
from models.reranker import CrossEncoderReranker
from retrieval.bm25 import BM25Index
from retrieval.vector_store import VectorStore
from retrieval.hybrid import rrf
from rag.pipeline import ABSTAIN_RERANK_MIN


def auroc(pos: np.ndarray, neg: np.ndarray) -> float:
    """P(score_pos > score_neg), ties count half (Mann-Whitney)."""
    allv = np.concatenate([pos, neg]); ranks = allv.argsort().argsort() + 1.0
    for v in np.unique(allv):                      # average ranks over ties
        m = allv == v
        if m.sum() > 1: ranks[m] = ranks[m].mean()
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def rates(thr: float, ans: np.ndarray, unans: np.ndarray) -> dict:
    return {"threshold": round(float(thr), 3),
            "answer_rate_on_answerable": float((ans >= thr).mean()),      # want high
            "abstain_rate_on_unanswerable": float((unans < thr).mean()),   # want high
            "balanced_accuracy": float(((ans >= thr).mean() + (unans < thr).mean()) / 2)}


def bootstrap_ci(fn, n, iters=1000, seed=0):
    rng = np.random.default_rng(seed); vals = [fn(rng.integers(0, n, n)) for _ in range(iters)]
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def run(dataset="scifact", top_final=8, rerank_top=50, max_dev=150):
    corpus, queries, train_q, test_q = load_beir(dataset)
    ids = list(corpus); texts = [corpus[i] for i in ids]
    emb, ce = Embedder("minilm"), CrossEncoderReranker()
    bm = BM25Index().build(ids, texts); vs = VectorStore(emb.dim, emb.name); vs.add(ids, emb.encode(texts))
    dev_q = dict(itertools.islice(train_q.items(), max_dev))

    def scores(qrels):
        a, u, a_hit = [], [], []
        for q, gold in qrels.items():
            b = bm.search(queries[q], 100); d = vs.search(emb.encode([queries[q]], is_query=True)[0], 100)
            fused = [c for c, _ in rrf([[c for c, _ in b], [c for c, _ in d]], [1.0, 1.0], 60)]
            for variant, pool in (("a", fused), ("u", [c for c in fused if c not in gold])):
                head = pool[:rerank_top]
                s = np.sort(ce.score(queries[q], [corpus[c] for c in head]))[::-1][:top_final]
                (a if variant == "a" else u).append(float(s[0]))
            a_hit.append(any(c in gold for c in fused[:rerank_top]))   # gold actually retrievable
        return np.array(a), np.array(u), np.array(a_hit)

    da, du, _ = scores(dev_q)
    ta, tu, thit = scores(test_q)
    # choose threshold on DEV: maximise balanced accuracy over observed score values
    cand = np.unique(np.concatenate([da, du]))
    best = max(cand, key=lambda t: rates(t, da, du)["balanced_accuracy"])
    out = {"dataset": dataset, "protocol": "gold-removal (see module docstring)", "signal": "max cross-encoder logit over top-%d reranked" % top_final,
           "dev_queries": len(da), "test_queries": len(ta),
           "auroc_dev": auroc(da, du), "auroc_test": auroc(ta, tu),
           "auroc_test_95ci": bootstrap_ci(lambda i: auroc(ta[i], tu[i]), len(ta)),
           "score_summary_test": {"answerable_median": float(np.median(ta)), "unanswerable_median": float(np.median(tu))},
           "current_threshold_test": rates(ABSTAIN_RERANK_MIN, ta, tu),
           "dev_tuned_threshold_test": rates(best, ta, tu),
           "dev_tuned_threshold_dev": rates(best, da, du),
           "answerable_gold_in_candidates_frac_test": float(thit.mean()),
           "caveats": ["Incomplete qrels => abstain_rate_on_unanswerable is a lower bound.",
                       "Claims-as-queries, single dataset, single run (CI = bootstrap over queries only).",
                       "ms-marco cross-encoder logits are uncalibrated; threshold is dataset/model specific."]}
    (OUT_DIR / "evaluations").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "evaluations" / f"abstention_{dataset}.json").write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
