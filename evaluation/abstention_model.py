"""Multi-signal abstention classifier (logistic regression) vs the single rerank-score baseline.
Same gold-removal protocol as abstention_eval. Fit on DEV only; report on held-out TEST."""
from __future__ import annotations
import json, itertools, re
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from common import OUT_DIR
from evaluation.retrieval_eval import load_beir
from evaluation.abstention_eval import auroc, rates, bootstrap_ci
from models.embeddings import Embedder
from models.reranker import CrossEncoderReranker
from retrieval.bm25 import BM25Index
from retrieval.vector_store import VectorStore
from retrieval.hybrid import rrf

W = re.compile(r"[a-z0-9]{4,}")
NAMES = ["rerank_top1", "rerank_top3_mean", "rerank_gap12", "n_above_0", "dense_top", "bm25_top_norm", "query_term_cov", "overlap_both"]


def feats(q, b, d, fused, corpus, ce, rerank_top=50):
    head = fused[:rerank_top]; s = np.sort(ce.score(q, [corpus[c] for c in head]))[::-1]
    order = np.argsort(-ce.score(q, [corpus[c] for c in head])); top = corpus[head[order[0]]].lower()
    qt = set(W.findall(q.lower())); cov = len([t for t in qt if t in top]) / max(len(qt), 1)
    bs = [x for _, x in b]; ds = [x for _, x in d]
    both = len(set(c for c, _ in b[:10]) & set(c for c, _ in d[:10])) / 10
    return [s[0], s[:3].mean(), s[0] - s[1], float((s > 0).sum()), ds[0], bs[0] / (np.mean(bs[:10]) + 1e-9), cov, both]


def collect(qrels, queries, corpus, bm, vs, emb, ce):
    X, y = [], []
    for q, gold in qrels.items():
        b = bm.search(queries[q], 100); d = vs.search(emb.encode([queries[q]], is_query=True)[0], 100)
        for label, drop in ((1, set()), (0, set(gold))):
            bb = [x for x in b if x[0] not in drop]; dd = [x for x in d if x[0] not in drop]
            fused = [c for c, _ in rrf([[c for c, _ in bb], [c for c, _ in dd]], [1.0, 1.0], 60)]
            X.append(feats(queries[q], bb, dd, fused, corpus, ce)); y.append(label)
    return np.array(X), np.array(y)


def run(max_dev=150):
    corpus, queries, train_q, test_q = load_beir("scifact")
    ids = list(corpus); texts = [corpus[i] for i in ids]
    emb, ce = Embedder("minilm"), CrossEncoderReranker()
    bm = BM25Index().build(ids, texts); vs = VectorStore(emb.dim, emb.name); vs.add(ids, emb.encode(texts))
    dev_q = dict(itertools.islice(train_q.items(), max_dev))
    Xd, yd = collect(dev_q, queries, corpus, bm, vs, emb, ce); Xt, yt = collect(test_q, queries, corpus, bm, vs, emb, ce)
    clf = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=1000)).fit(Xd, yd)
    pt = clf.predict_proba(Xt)[:, 1]; pd_ = clf.predict_proba(Xd)[:, 1]
    ta, tu = pt[yt == 1], pt[yt == 0]
    cand = np.unique(pd_); thr = max(cand, key=lambda t: rates(t, pd_[yd == 1], pd_[yd == 0])["balanced_accuracy"])
    single = {n: auroc(Xt[yt == 1][:, i], Xt[yt == 0][:, i]) for i, n in enumerate(NAMES)}
    out = {"features": NAMES, "single_feature_auroc_test": single,
           "model_auroc_test": auroc(ta, tu),
           "model_auroc_test_95ci": bootstrap_ci(lambda i: auroc(ta[i % len(ta)], tu[i % len(tu)]), len(ta)),
           "model_dev_tuned_threshold_test": rates(thr, ta, tu),
           "coefficients": dict(zip(NAMES, map(float, clf[-1].coef_[0])))}
    (OUT_DIR / "evaluations" / "abstention_model_scifact.json").write_text(json.dumps(out, indent=2))
    return out

if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
