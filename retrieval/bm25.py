"""BM25 over chunks. Tokeniser keeps chemical formulae, gene symbols and identifiers intact."""
from __future__ import annotations
import pickle, re
from pathlib import Path
import numpy as np
from rank_bm25 import BM25Okapi

_TOK = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-\.\+']*[A-Za-z0-9\+]|[A-Za-z0-9]")
STOP = set("a an the of and or in on for to with by is are was were be been this that these those as at from it its we our can".split())


def tokenize(t: str) -> list[str]:
    toks = [x.lower().rstrip(".") for x in _TOK.findall(t)]
    return [x for x in toks if x not in STOP]


class BM25Index:
    def __init__(self, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.ids: list[str] = []
        self.tokens: list[list[str]] = []
        self.bm25: BM25Okapi | None = None

    def build(self, ids: list[str], texts: list[str]):
        self.ids, self.tokens = list(ids), [tokenize(t) for t in texts]
        self.bm25 = BM25Okapi(self.tokens, k1=self.k1, b=self.b)
        return self

    def search(self, query: str, k=100, allowed: set[str] | None = None) -> list[tuple[str, float]]:
        q = tokenize(query)
        if not q or self.bm25 is None:
            return []
        s = self.bm25.get_scores(q)
        if allowed is not None:
            mask = np.fromiter((i in allowed for i in self.ids), bool, len(self.ids))
            s = np.where(mask, s, -np.inf)
        top = np.argpartition(-s, min(k, len(s) - 1))[:k]
        top = top[np.argsort(-s[top])]
        return [(self.ids[i], float(s[i])) for i in top if np.isfinite(s[i]) and s[i] > 0]

    def save(self, path: Path):
        path.mkdir(parents=True, exist_ok=True)
        with open(path / "bm25.pkl", "wb") as f:
            pickle.dump({"ids": self.ids, "tokens": self.tokens, "k1": self.k1, "b": self.b}, f)

    @classmethod
    def load(cls, path: Path) -> "BM25Index":
        d = pickle.load(open(path / "bm25.pkl", "rb"))
        o = cls(d["k1"], d["b"]); o.ids, o.tokens = d["ids"], d["tokens"]
        o.bm25 = BM25Okapi(o.tokens, k1=o.k1, b=o.b)
        return o
