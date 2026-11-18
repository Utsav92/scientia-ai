import numpy as np
from extraction.compare import compare, entity_overlap, candidate_tensions

def ev(t): return {"text": t, "quote": t, "chunk_ids": []}
def ent(c): return {"text": c, "type": "METHOD", "canonical": c}

EX = {
    "A": {"method": "rules", "findings": [ev("Method X improves accuracy.")], "methodology": ev("We use X."), "entities": [ent("x"), ent("acc"), ent("onlya")]},
    "B": {"method": "rules", "findings": [ev("Method X does not improve accuracy.")], "methodology": None, "entities": [ent("x"), ent("acc"), ent("onlyb")]},
    "C": {"method": "rules", "findings": [ev("Unrelated result.")], "entities": [ent("zzz")]},
}

class FakeNLI:
    def probs(self, p, h):
        return np.array([[0.95, 0.03, 0.02] if ("not" in a) != ("not" in b) else [0.01, 0.9, 0.09] for a, b in zip(p, h)])

def test_overlap_exact_and_unique():
    o = entity_overlap({k: EX[k] for k in "AB"})
    assert o["shared_by_all"] == ["acc", "x"] and o["unique"] == {"A": ["onlya"], "B": ["onlyb"]}
    assert o["pairs"][0]["jaccard"] == 0.5

def test_missing_dimension_is_empty_not_invented():
    t = compare(EX, {}, None)["dimensions"]
    assert t["methodology"]["B"] == [] and t["research_question"]["A"] == []

def test_tensions_need_shared_entity_and_are_labelled():
    r = candidate_tensions(EX, FakeNLI())
    assert r["pairs_checked"] == 1 and len(r["candidates"]) == 1 and "caveat" in r
    assert {r["candidates"][0]["paper_a"], r["candidates"][0]["paper_b"]} == {"A", "B"}   # C shares nothing

def test_no_nli_means_no_tension_claims():
    assert compare(EX, {}, None)["tensions"] is None
