"""Lazy, cached embedding backend (MPS/CPU) with throughput tracking."""
from __future__ import annotations
import time
import numpy as np
from common import load_config, get_device

_CACHE: dict[str, "Embedder"] = {}


class Embedder:
    def __init__(self, key_or_name: str = "minilm", max_seq_length: int = 256, batch_size: int = 32):
        cfg = load_config("models")["embedding"]["candidates"]
        spec = cfg.get(key_or_name, {"name": key_or_name})
        self.key, self.name = key_or_name, spec["name"]
        self.query_prefix = spec.get("query_prefix", "")
        self.batch_size, self.max_seq_length = batch_size, max_seq_length
        self._model = None
        self.stats = {"texts": 0, "seconds": 0.0}

    @property
    def model(self):
        if self._model is None:  # lazy init keeps API start-up light
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.name, device=get_device())
            self._model.max_seq_length = self.max_seq_length
        return self._model

    @property
    def dim(self) -> int:
        return self.model.get_sentence_embedding_dimension()

    def encode(self, texts: list[str], is_query: bool = False, show_progress=False) -> np.ndarray:
        if is_query and self.query_prefix:
            texts = [self.query_prefix + t for t in texts]
        t0 = time.perf_counter()
        v = self.model.encode(texts, batch_size=self.batch_size, normalize_embeddings=True,
                              convert_to_numpy=True, show_progress_bar=show_progress)
        self.stats["texts"] += len(texts); self.stats["seconds"] += time.perf_counter() - t0
        return v.astype("float32")

    @property
    def throughput(self) -> float:
        return self.stats["texts"] / self.stats["seconds"] if self.stats["seconds"] else 0.0


def get_embedder(key: str = "minilm", **kw) -> Embedder:
    k = f"{key}:{sorted(kw.items())}"
    if k not in _CACHE:
        _CACHE[k] = Embedder(key, **kw)
    return _CACHE[k]
