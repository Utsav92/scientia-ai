"""NLI wrapper (entailment / neutral / contradiction). A baseline signal only - never proof."""
from __future__ import annotations
import numpy as np
from common import load_config, get_device

_M = {}


class NLI:
    def __init__(self, name=None):
        self.name = name or load_config("models")["nli"]["default"]["name"]
        self._m = None

    @property
    def model(self):
        if self._m is None:
            from sentence_transformers import CrossEncoder
            self._m = CrossEncoder(self.name, device=get_device())
        return self._m

    def probs(self, premises: list[str], hypotheses: list[str]) -> np.ndarray:
        """Returns [n,3] softmax probs in the model's label order, mapped to (contradiction, entailment, neutral)."""
        logits = np.asarray(self.model.predict(list(zip(premises, hypotheses)), apply_softmax=True, show_progress_bar=False))
        id2 = {int(k): v.lower() for k, v in self.model.model.config.id2label.items()}
        order = [next(i for i, l in id2.items() if l.startswith(p)) for p in ("contra", "entail", "neutral")]
        return logits[:, order]


def get_nli() -> NLI:
    if "nli" not in _M:
        _M["nli"] = NLI()
    return _M["nli"]
