"""Fine-tune the MiniLM embedder on SciFact TRAIN qrels (real supervision, not weak labels).

Protocol: train on train-qrels queries EXCEPT the first 150 (those were the DEV set used for RRF tuning and
are used here for early stopping). Report dense-only metrics on the untouched BEIR TEST split, base vs tuned.
Loss: MultipleNegativesRanking with one mined hard negative (base-dense rank 10..50, not a positive).
Caveat: SciFact is small (~800 train queries); numbers are a single seed, no CI.
"""
from __future__ import annotations
import itertools, json, random, time
import numpy as np, torch
from sentence_transformers import SentenceTransformer
from common import OUT_DIR, get_device, load_config
from evaluation.retrieval_eval import load_beir, metrics

SEED = 13


def encode(model, texts, bs=64):
    return model.encode(texts, batch_size=bs, normalize_embeddings=True, convert_to_numpy=True)


def dense_eval(model, corpus_ids, corpus_vecs, queries, qrels):
    qs = list(qrels)
    qv = encode(model, [queries[q] for q in qs])
    top = np.argsort(-(qv @ corpus_vecs.T), axis=1)[:, :100]
    return metrics({q: [corpus_ids[j] for j in top[i]] for i, q in enumerate(qs)}, qrels)


def run(epochs=None, lr=None, bs=None):
    cfg = load_config("training")["embeddings"]
    epochs, lr, bs = epochs or 3, lr or cfg["lr"], bs or cfg["batch_size"]
    random.seed(SEED); torch.manual_seed(SEED)
    corpus, queries, train_q, test_q = load_beir("scifact")
    ids = list(corpus); texts = [corpus[i] for i in ids]
    dev_q = dict(itertools.islice(train_q.items(), 150))
    fit_q = {q: r for q, r in train_q.items() if q not in dev_q}
    dev = get_device()
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device=dev); model.max_seq_length = 256
    base_vecs = encode(model, texts)
    base = {"dev": dense_eval(model, ids, base_vecs, queries, dev_q), "test": dense_eval(model, ids, base_vecs, queries, test_q)}
    print("base", json.dumps({k: round(v["ndcg@10"], 4) for k, v in base.items()}))

    # hard negatives from the BASE model
    fq = list(fit_q); qv = encode(model, [queries[q] for q in fq])
    rank = np.argsort(-(qv @ base_vecs.T), axis=1)[:, :50]
    triples = []
    for i, q in enumerate(fq):
        negs = [ids[j] for j in rank[i, 10:50] if ids[j] not in fit_q[q]]
        for pos in fit_q[q]:
            triples.append((queries[q], corpus[pos], corpus[random.choice(negs)] if negs else None))
    print(f"{len(fit_q)} train queries -> {len(triples)} triples")

    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    steps = epochs * (len(triples) // bs); warm = max(1, int(0.1 * steps))
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min((s + 1) / warm, max(0.0, (steps - s) / max(1, steps - warm))))

    def emb(batch):
        f = model.tokenize(batch); f = {k: v.to(dev) for k, v in f.items() if torch.is_tensor(v)}
        return torch.nn.functional.normalize(model(f)["sentence_embedding"], dim=-1)

    best, best_state, bad, hist = -1, None, 0, []
    for ep in range(epochs):
        model.train(); random.shuffle(triples); losses = []
        for b in range(0, len(triples) - bs + 1, bs):
            batch = triples[b:b + bs]
            q = emb([t[0] for t in batch]); p = emb([t[1] for t in batch])
            docs = p if any(t[2] is None for t in batch) else torch.cat([p, emb([t[2] for t in batch])])
            loss = torch.nn.functional.cross_entropy(q @ docs.T * 20.0, torch.arange(len(batch), device=dev))
            opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step(); sched.step()
            losses.append(loss.item())
        model.eval()
        with torch.no_grad():
            d = dense_eval(model, ids, encode(model, texts), queries, dev_q)["ndcg@10"]
        hist.append({"epoch": ep + 1, "train_loss": float(np.mean(losses)), "dev_ndcg@10": d})
        print(hist[-1])
        if d > best: best, bad, best_state = d, 0, {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= cfg.get("patience", 2): break
    model.load_state_dict(best_state); model.eval()
    with torch.no_grad():
        tuned_vecs = encode(model, texts)
        tuned = {"dev": dense_eval(model, ids, tuned_vecs, queries, dev_q), "test": dense_eval(model, ids, tuned_vecs, queries, test_q)}
    out_dir = OUT_DIR / "models" / "minilm_scifact_ft"; model.save(str(out_dir))
    res = {"base": base, "tuned": tuned, "history": hist, "epochs_max": epochs, "lr": lr, "batch_size": bs, "seed": SEED,
           "n_train_queries": len(fit_q), "n_triples": len(triples), "device": dev, "saved_to": str(out_dir),
           "note": "single seed, no CI; dev queries used for early stopping only; test untouched until final eval"}
    (OUT_DIR / "evaluations" / "embedding_finetune_scifact.json").write_text(json.dumps(res, indent=2))
    print("tuned", json.dumps({k: round(v["ndcg@10"], 4) for k, v in tuned.items()}))
    return res


if __name__ == "__main__":
    run()
