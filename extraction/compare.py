"""Cross-paper comparison built only from grounded extractions.

Every cell is an `Evidenced` item (statement + verbatim quote), never newly generated text. Entity overlap is exact on
canonical ids. Candidate tensions come from an NLI model run on finding pairs that share an entity; they are a baseline
signal for a human to check, never a verdict.
"""
from __future__ import annotations
from itertools import combinations

DIMENSIONS = ["research_question", "methodology", "datasets", "findings", "quantitative_results", "limitations", "future_work"]
MAX_PAIRS = 200          # bound NLI cost
MIN_CONTRA = 0.85


def _items(ex: dict, key: str) -> list[dict]:
    v = ex.get(key)
    return [v] if isinstance(v, dict) else list(v or [])


def entity_overlap(extractions: dict[str, dict]) -> dict:
    per = {pid: {e["canonical"]: e for e in ex.get("entities", [])} for pid, ex in extractions.items()}
    ids = list(per)
    shared_all = sorted(set.intersection(*(set(m) for m in per.values()))) if per else []
    pairs = []
    for a, b in combinations(ids, 2):
        s = sorted(set(per[a]) & set(per[b]))
        union = set(per[a]) | set(per[b])
        pairs.append({"a": a, "b": b, "shared": s[:50], "n_shared": len(s), "jaccard": round(len(s) / len(union), 3) if union else 0.0})
    unique = {pid: sorted(set(m) - set().union(*(set(o) for q, o in per.items() if q != pid)))[:50] for pid, m in per.items()}
    return {"shared_by_all": shared_all[:50], "pairs": pairs, "unique": unique}


def candidate_tensions(extractions: dict[str, dict], nli) -> dict:
    """NLI over finding pairs from different papers that share >=1 canonical entity."""
    ents = {pid: {e["canonical"] for e in ex.get("entities", [])} for pid, ex in extractions.items()}
    cand = []
    for a, b in combinations(extractions, 2):
        common = ents[a] & ents[b]
        if not common: continue
        for fa in _items(extractions[a], "findings"):
            for fb in _items(extractions[b], "findings"):
                cand.append((a, b, fa, fb, sorted(common)[:5]))
    truncated = len(cand) > MAX_PAIRS
    cand = cand[:MAX_PAIRS]
    out = []
    if cand:
        pa = [c[2]["text"] for c in cand] + [c[3]["text"] for c in cand]
        pb = [c[3]["text"] for c in cand] + [c[2]["text"] for c in cand]
        p = nli.probs(pa, pb)
        n = len(cand)
        for i, (a, b, fa, fb, common) in enumerate(cand):
            contra = float(max(p[i][0], p[i + n][0]))
            if contra >= MIN_CONTRA:
                out.append({"paper_a": a, "paper_b": b, "a": fa, "b": fb, "shared_entities": common, "contradiction_prob": round(contra, 3)})
    out.sort(key=lambda t: -t["contradiction_prob"])
    return {"candidates": out[:20], "pairs_checked": len(cand), "truncated": truncated, "min_prob": MIN_CONTRA,
            "caveat": "NLI baseline on sentence pairs. Candidates may differ in conditions, scope or dataset; read both quotes before concluding anything."}


def compare(extractions: dict[str, dict], titles: dict[str, str | None], nli=None) -> dict:
    table = {d: {pid: _items(ex, d) for pid, ex in extractions.items()} for d in DIMENSIONS}
    return {"papers": [{"paper_id": pid, "title": titles.get(pid), "method": ex.get("method"), "n_entities": len(ex.get("entities", []))} for pid, ex in extractions.items()],
            "dimensions": table, "entities": entity_overlap(extractions),
            "tensions": candidate_tensions(extractions, nli) if nli else None}
