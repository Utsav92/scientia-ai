"""Relation extraction: sentence-level co-occurrence of typed entities with a cue verb. Rule baseline; evidence = the sentence."""
from __future__ import annotations
import re
from .entities import extract_entities, dedupe
from .findings import sentences

CUES = {
    "EVALUATED_ON": r"\b(?:on|evaluated|tested|benchmark(?:ed)?|trained on|using the)\b",
    "USES_METHOD": r"\b(?:using|used|use|employ(?:ed)?|apply|applied|based on|with|via)\b",
    "MEASURES": r"\b(?:achiev\w*|report\w*|reach\w*|measur\w*|yield\w*|obtain\w*)\b",
}
METHOD_T, DATASET_T, METRIC_T = {"METHOD", "MODEL", "ALGORITHM"}, {"DATASET"}, {"METRIC"}


def extract_relations(text: str) -> list[dict]:
    rels, seen = [], set()
    for s in sentences(text):
        ents = dedupe(extract_entities(s))
        for a in ents:
            for b in ents:
                if a is b: continue
                if a.type in METHOD_T and b.type in DATASET_T and re.search(CUES["EVALUATED_ON"], s, re.I): rel = "EVALUATED_ON"
                elif a.type in METHOD_T and b.type in METRIC_T and re.search(CUES["MEASURES"], s, re.I): rel = "MEASURES"
                else: continue
                k = (a.canonical, rel, b.canonical)
                if k in seen: continue
                seen.add(k); rels.append({"head": a.canonical, "head_type": a.type, "rel": rel, "tail": b.canonical, "tail_type": b.type, "evidence": s})
    return rels
