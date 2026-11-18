"""Exact + near duplicate detection (versions of the same work)."""
from __future__ import annotations
import hashlib, re

_NORM = re.compile(r"[^a-z0-9]+")


def content_hash(text: str) -> str:
    return hashlib.sha1(_NORM.sub(" ", text.lower()).strip().encode()).hexdigest()


def shingles(text: str, k: int = 5, limit: int = 400) -> set[int]:
    w = _NORM.sub(" ", text.lower()).split()[:limit]
    return {hash(" ".join(w[i:i + k])) & 0xFFFFFFFF for i in range(max(1, len(w) - k + 1))}


class NearDupIndex:
    """Cheap MinHash-style signature with banding; good enough for a dedup pass on 1e5 docs."""
    def __init__(self, bands=8, rows=2, threshold=0.8):
        self.bands, self.rows, self.th = bands, rows, threshold
        self.buckets: dict[tuple, list[str]] = {}
        self.sets: dict[str, set[int]] = {}

    def _sig(self, s: set[int]):
        n = self.bands * self.rows
        return [min(((x * (2 * i + 1) + i * 0x9E3779B1) & 0xFFFFFFFF) for x in s) if s else 0 for i in range(n)]

    def check_and_add(self, doc_id: str, text: str) -> str | None:
        """Return id of an existing near-duplicate, else register and return None."""
        s = shingles(text)
        sig = self._sig(s)
        keys = [(b, tuple(sig[b * self.rows:(b + 1) * self.rows])) for b in range(self.bands)]
        for k in keys:
            for other in self.buckets.get(k, []):
                o = self.sets[other]
                if s and o and len(s & o) / len(s | o) >= self.th:
                    return other
        self.sets[doc_id] = s
        for k in keys:
            self.buckets.setdefault(k, []).append(doc_id)
        return None
