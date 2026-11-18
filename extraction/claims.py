"""Claim extraction = grounded findings + quantitative results, as atomic evidence-linked records
(used later by contradiction detection)."""
from __future__ import annotations
from .schemas import PaperExtraction


def claims_from(ex: PaperExtraction, title: str | None = None, year: int | None = None) -> list[dict]:
    out = []
    for kind, items in (("finding", ex.findings), ("quantitative", ex.quantitative_results)):
        for i, f in enumerate(items):
            out.append({"claim_id": f"{ex.paper_id}:{kind[0]}{i}", "paper_id": ex.paper_id, "kind": kind, "text": f.text, "quote": f.quote,
                        "chunk_ids": f.chunk_ids, "title": title, "year": year})
    return out
