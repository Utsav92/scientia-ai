"""Cross-encoder reranker: scores [QUESTION, PASSAGE] pairs."""
from __future__ import annotations
import numpy as np
from common import load_config, get_device

_CACHE: dict = {}


class CrossEncoderReranker:
    def __init__(self, key_or_path: str = "minilm_ce", batch_size: int = 16, max_length: int = 384):
        cands = load_config("models")["reranker"]["candidates"]
        self.name = cands[key_or_path]["name"] if key_or_path in cands else key_or_path
        self.batch_size, self.max_length = batch_size, max_length
        self._m = None

    @property
    def model(self):
        if self._m is None:
            from sentence_transformers import CrossEncoder
            self._m = CrossEncoder(self.name, device=get_device(), max_length=self.max_length)
        return self._m

    def score(self, query: str, passages: list[str]) -> np.ndarray:
        if not passages:
            return np.array([])
        return np.asarray(self.model.predict([(query, p) for p in passages], batch_size=self.batch_size,
                                             show_progress_bar=False), dtype="float32")


def get_reranker(key="minilm_ce") -> CrossEncoderReranker:
    if key not in _CACHE:
        _CACHE[key] = CrossEncoderReranker(key)
    return _CACHE[key]
