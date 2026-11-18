"""FAISS inner-product store with incremental add and on-disk persistence."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import faiss


class VectorStore:
    def __init__(self, dim: int, model_name: str = ""):
        self.dim, self.model_name = dim, model_name
        self.index = faiss.IndexFlatIP(dim)   # exact; fine to ~1e6 chunks on 24 GB. Swap for HNSW/IVF beyond that.
        self.ids: list[str] = []

    def add(self, ids: list[str], vecs: np.ndarray):
        assert vecs.shape[1] == self.dim and len(ids) == len(vecs)
        self.index.add(np.ascontiguousarray(vecs, dtype="float32")); self.ids += list(ids)

    def search(self, qvec: np.ndarray, k=100, allowed: set[str] | None = None):
        n = len(self.ids)
        if n == 0:
            return []
        kk = n if allowed is not None else min(k, n)
        D, I = self.index.search(np.ascontiguousarray(qvec.reshape(1, -1), dtype="float32"), kk)
        out = [(self.ids[i], float(d)) for d, i in zip(D[0], I[0]) if i >= 0 and (allowed is None or self.ids[i] in allowed)]
        return out[:k]

    def save(self, path: Path):
        path.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(path / "faiss.index"))
        (path / "vec_meta.json").write_text(json.dumps({"ids": self.ids, "dim": self.dim, "model": self.model_name}))

    @classmethod
    def load(cls, path: Path) -> "VectorStore":
        m = json.loads((path / "vec_meta.json").read_text())
        o = cls(m["dim"], m["model"]); o.ids = m["ids"]; o.index = faiss.read_index(str(path / "faiss.index"))
        return o

    def size_bytes(self, path: Path) -> int:
        return sum(f.stat().st_size for f in path.glob("*") if f.is_file())
