"""Question -> understanding -> hybrid retrieval -> rerank -> evidence selection -> generation -> verification."""
from __future__ import annotations
import re, time
from retrieval.hybrid import Retriever
from .prompts import build_prompt
from .citations import build_citation_table
from .verification import verify_answer, revise_answer
from .synthesis import get_llm, Extractive

ABSTAIN_RERANK_MIN = -3.0   # UNCALIBRATED heuristic on ms-marco logits; documented in README
MODES = {
    "compare": r"\bcompar|\bversus\b|\bvs\.?\b|\bdifference between\b",
    "trend": r"\bhow has\b|\bevolv|\bover time\b|\btrend",
    "gap": r"\blimitation|\bgap|\bopen problem|\bchallenge",
    "summarize": r"\bsummari[sz]e\b",
    "papers": r"\bwhich (recent )?papers\b|\bfind papers\b",
}


_GENERIC = set("the latest recent evidence models model approach approaches method methods using based scientific data generation study studies new".split())


def _core_terms(phrase: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9\-]{4,}", phrase.lower()) if w not in _GENERIC]


def _mentions(text: str, terms: list[str]) -> bool:
    """Conjunctive: ALL core terms must co-occur in the passage (stem = word minus plural 's')."""
    t = text.lower()
    return bool(terms) and all(w.rstrip("s") in t for w in terms)


def understand(q: str) -> dict:
    q = " ".join(q.split())
    mode = next((m for m, rx in MODES.items() if re.search(rx, q, re.I)), "direct")
    sides = None
    m = re.search(r"(?:compare\s+)?(.+?)\s+(?:versus|vs\.?|and|with)\s+(.+?)(?:\s+(?:in|for|on)\s+(.+))?$", re.sub(r"^.*?(?:compare|evidence for)\s+(?:the latest evidence for\s+)?", "", q, flags=re.I) if mode == "compare" else "", re.I)
    if mode == "compare" and m:
        ctx = m.group(3) or ""
        sides = [f"{m.group(1)} {ctx}".strip(), f"{m.group(2)} {ctx}".strip()]
        cores = [_core_terms(m.group(1)), _core_terms(m.group(2))]
    else:
        cores = None
    return {"question": q, "mode": mode, "sides": sides, "cores": cores,
            "temporal_claim_note": "Corpus is a static snapshot; 'latest' means latest in the indexed corpus, not the current literature." if re.search(r"latest|recent|current|new", q, re.I) else None}


def answer_question(question: str, retriever: Retriever, k=8, llm=None, domains=None, year_min=None, year_max=None,
                    nli=None, verify=True, full_text_only=False, doc_ids=None) -> dict:
    t0 = time.perf_counter()
    u = understand(question)
    queries = u["sides"] or [question]
    per = max(3, k // len(queries))
    ev, seen = [], set()
    for q in queries:
        res = retriever.search(q, "hybrid_rerank", k=per * 2, domains=domains, year_min=year_min, year_max=year_max, full_text_only=full_text_only, doc_ids=doc_ids)
        n = 0
        for e in res["results"]:
            if e.chunk_id in seen: continue
            seen.add(e.chunk_id); e.metadata["query_side"] = q; ev.append(e); n += 1
            if n >= per: break
    cit = build_citation_table(ev)
    uncovered = []
    if u["cores"]:
        for side_q, core in zip(u["sides"], u["cores"]):
            side_ev = [e for e in ev if e.metadata.get("query_side") == side_q]
            if core and not any(_mentions((e.title or "") + " " + e.passage, core) for e in side_ev):
                uncovered.append(" ".join(core))
    best = max((e.scores.get("rerank", -99) for e in ev), default=-99)
    out = {"understanding": u, "citations": cit, "retrieved": [e.to_dict() for e in ev], "llm": None}
    if uncovered:
        out.update(answer="Cannot compare: the indexed corpus contains no passages mentioning " + "; ".join(f"'{x}'" for x in uncovered)
                          + ". The retrieved passages below are only loosely related and were not used to form a comparison.",
                   abstained=True, verification=None, coverage={"evidence_passages": len(ev), "uncovered_sides": uncovered})
    elif u["mode"] == "papers" and ev and best >= ABSTAIN_RERANK_MIN:
        seen_d, lines = set(), []
        for n, e in enumerate(ev, 1):
            if e.doc_id in seen_d: continue
            seen_d.add(e.doc_id)
            lines.append(f"{e.title} ({e.metadata.get('year') or 'year n/a'}) [{n}]")
        out.update(answer="Papers in the indexed corpus most relevant to the question (ranked by retrieval + reranker; not exhaustive): " + "; ".join(lines) + ".",
                   abstained=False, verification=None, llm="paper-list",
                   coverage={"evidence_passages": len(ev), "distinct_papers": len(seen_d), "best_rerank_score": best},
                   note="Corpus is a static snapshot; this lists indexed papers, not the current literature.")
    elif not ev or best < ABSTAIN_RERANK_MIN:
        out.update(answer="The indexed corpus does not contain sufficient evidence to answer this question.", abstained=True,
                   verification=None, coverage={"evidence_passages": len(ev), "best_rerank_score": best if ev else None})
    else:
        llm = llm or get_llm()
        out["llm"] = llm.name
        if isinstance(llm, Extractive):
            draft = llm.answer(question, cit)
        else:
            draft = llm.generate(build_prompt(question, [(n, c["title"] or "", c["section"] or "", c["passage"]) for n, c in cit.items()]))
        if not re.search(r"\[\d+", draft):   # one bounded retry: model ignored the citation format
            draft = llm.generate(build_prompt(question, [(n, c["title"] or "", c["section"] or "", c["passage"]) for n, c in cit.items()])
                                 + "\n(Reminder: every sentence MUST end with a [n] citation before its period.)") if not isinstance(llm, Extractive) else draft
        report = verify_answer(draft, cit, nli) if verify else None
        final = revise_answer(draft, report) if report else draft
        if not final.strip():
            final, out["abstained"] = "No claim could be verified against the retrieved passages.", True
        else:
            out["abstained"] = False
        out.update(draft=draft, answer=final, verification=report,
                   coverage={"evidence_passages": len(ev), "distinct_papers": len({e.doc_id for e in ev}), "best_rerank_score": best})
        if u["temporal_claim_note"]: out["note"] = u["temporal_claim_note"]
    out["latency_s"] = round(time.perf_counter() - t0, 2)
    return out
