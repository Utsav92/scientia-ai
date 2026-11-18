"""Citation verification: for each claim, fetch the cited passage and test support.

Support = NLI entailment of claim by cited passage(s) AND minimal lexical grounding (guards against
NLI neutral-vs-contradiction confusion and against numbers that do not appear in the source).
"""
from __future__ import annotations
import re
from .citations import split_claims

_NUM = re.compile(r"\d+(?:\.\d+)?%?")
_W = re.compile(r"[a-z0-9]{4,}")


def lexical_overlap(claim: str, passage: str) -> float:
    c = set(_W.findall(re.sub(r"\[\d+\]", "", claim.lower())))
    return len(c & set(_W.findall(passage.lower()))) / len(c) if c else 0.0


def numbers_grounded(claim: str, passage: str) -> bool:
    claim_nums = set(_NUM.findall(re.sub(r"\[\d+\]", "", claim)))
    return all(n in passage for n in claim_nums)


_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(])")


def premise_windows(passage: str, max_windows: int = 24) -> list[str]:
    """Sentence and adjacent-sentence windows. Sentence-pair NLI models are unreliable on long multi-sentence
    premises (measured: a passage containing the claim verbatim scored 'neutral' 0.996), so we align at sentence level."""
    sents = [x.strip() for x in _SPLIT.split(passage.replace("\n", " ")) if len(x.strip()) > 20]
    wins = sents + [sents[i] + " " + sents[i + 1] for i in range(len(sents) - 1)]
    return wins[:max_windows] or [passage[:600]]


def verify_answer(answer: str, citations: dict[int, dict], nli=None, ent_threshold=0.5, min_overlap=0.35) -> dict:
    claims = split_claims(answer)
    results = []
    for c in claims:
        if c["is_interpretation"]:
            results.append({**c, "status": "interpretation", "support": None}); continue
        if not c["markers"]:
            results.append({**c, "status": "uncited", "support": None}); continue
        bad = [m for m in c["markers"] if m not in citations]
        if bad:
            results.append({**c, "status": "invalid_citation", "support": None, "bad_markers": bad}); continue
        cited_text = " ".join(citations[m]["passage"] for m in c["markers"])
        ent, overlap, num_ok = None, lexical_overlap(c["text"], cited_text), numbers_grounded(c["text"], cited_text)
        if nli is not None:
            hyp = re.sub(r"\[\d+\]", "", c["text"]).strip()
            best = 0.0
            for m in c["markers"]:
                wins = premise_windows(citations[m]["passage"])
                pr = nli.probs(wins, [hyp] * len(wins))
                best = max(best, float(pr[:, 1].max()))
            ent = best
        ok = num_ok and overlap >= min_overlap and (ent is None or ent >= ent_threshold or overlap >= 0.75)
        results.append({**c, "status": "supported" if ok else "unsupported", "support": {"entailment": ent, "lexical_overlap": round(overlap, 3), "numbers_grounded": num_ok}})
    factual = [r for r in results if r["status"] not in ("interpretation",)]
    n_sup = sum(r["status"] == "supported" for r in factual)
    return {"claims": results, "claim_support_rate": n_sup / len(factual) if factual else None,
            "unsupported": [r["text"] for r in results if r["status"] in ("unsupported", "uncited", "invalid_citation")]}


def revise_answer(answer: str, report: dict) -> str:
    """Remove statements that failed verification (never silently keep unsupported claims)."""
    drop = set(report["unsupported"])
    kept = [c["text"] for c in report["claims"] if c["text"] not in drop]
    return " ".join(kept)
