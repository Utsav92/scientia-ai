"""Document structure from the paper's own headings (ALL-CAPS, numbered, or well-known section names), with the most informative whole
sentences chosen per section. Works for research papers and for reports/plans alike. Nothing is generated: sentences are verbatim."""
from __future__ import annotations
import re
from collections import Counter
from extraction.findings import sentences, _QUANT, _unwrap

KNOWN = (r"abstract|summary|executive summary|introduction|background|overview|methods?|methodology|materials and methods|experimental(?: section)?|results?|"
         r"results and discussion|discussion|conclusions?|conclusions and future work|limitations|future work|recommendations|findings|analysis|approach|implementation|outlook")
ACRONYMS = {"NASA", "US", "USA", "LTV", "SLS", "ISS", "EVA", "ISRU", "HLS", "ESA", "JAXA", "CSA", "AI", "ML", "DNA", "RNA", "UK", "EU", "CO2", "GPS", "LED", "MRI", "CT"}
SMALL = {"a", "an", "the", "of", "and", "or", "for", "to", "in", "on", "at", "by", "with", "from", "vs"}
CUES = re.compile(r"\b(?:will|plans?|goals?|aims?|enable[sd]?|establish\w*|achiev\w*|demonstrat\w*|provid\w*|develop\w*|launch\w*|land\w*|return\w*|build\w*|requir\w*|result\w*|show\w*|found|propos\w*|present\w*|predict\w*|reach\w*|exceed\w*|improv\w*|support\w*|first|key|critical|primary|major)\b", re.I)
MAX_SECTIONS = 10


def pretty(h: str) -> str:
    h = re.sub(r"^\s*\d+(?:\.\d+)*\.?\s+", "", h).strip().rstrip(":")
    if not h.isupper(): return h
    out = []
    for i, w in enumerate(h.split()):
        core = re.sub(r"[’']S$", "", w); suf = "’s" if w != core else ""
        out.append((core if core in ACRONYMS else core.lower() if core.lower() in SMALL and i else core.capitalize()) + suf)
    return " ".join(out)


def detect(text: str, title: str = "") -> list[tuple[int, str]]:
    lines = text.split("\n"); counts = Counter(l.strip() for l in lines); t = title.strip().lower(); heads = []
    for i, l in enumerate(lines):
        s = l.strip()
        if not (4 <= len(s) <= 80) or counts[s] > 2 or s.endswith((".", ",", ";", "?", "”", '"')) or s.lower() == t or t.startswith(s.lower()) and len(s) > 12: continue
        if re.search(r"\s\d{1,3}$", s) and len(s) > 25: continue                                    # running header with page number
        if re.fullmatch(r"(?:\d+(?:\.\d+)*\.?\s+)?(?:" + KNOWN + r"):?", s, re.I) or re.match(r"^\d+(?:\.\d+)*\.?\s+[A-Z][A-Za-z ,:&’'-]{3,60}$", s) or (s.isupper() and 1 <= len(s.split()) <= 10 and re.search(r"[A-Z]{3}", s)):
            heads.append((i, s))
    return heads


def _complete(s: str) -> str | None:
    """A usable sentence starts like one and ends like one (fragments from layout breaks are skipped); bullet markers are dropped."""
    s = re.sub(r"^[•◦▪\-–*]\s*", "", s.strip())
    return s if s and (s[0].isupper() or s[0].isdigit() or s[0] in "“\"‘'(") and re.search(r"[.!?][\"')\]”’]?$", s) else None


def _clean_lines(text: str, title: str) -> str:
    """Drop running page headers/footers (lines containing the document title plus a page number, bare page numbers)."""
    t = title.strip().lower(); keep = []
    for ln in text.split("\n"):
        s = ln.strip()
        if re.fullmatch(r"\d{1,3}", s) or (t and len(t) > 12 and t in s.lower() and len(s) > len(t) and re.search(r"\d{1,3}\s*$", s)) or (t and s.lower() == t):
            continue
        keep.append(ln)
    return "\n".join(keep)


def _rank(sents: list[str], k: int) -> list[str]:
    scored = []
    sents = [c for c in (_complete(x) for x in sents) if c]
    for i, s in enumerate(sents):
        if len(s) < 45: continue
        sc = (2.0 if _QUANT.search(s) else 0) + (1.0 if CUES.search(s) else 0) + (1.5 if i == 0 else 0) + (0.5 if 60 <= len(s) <= 280 else -0.5) - (1.0 if s.count(",") > 6 else 0)
        scored.append((sc, i, s))
    top = sorted(scored, key=lambda x: (-x[0], x[1]))[:k]
    return [s for _, _, s in sorted(top, key=lambda x: x[1])]


def sections(text: str, title: str = "") -> list[dict]:
    """[{heading, sentences:[{text, quote}], n}] in document order; empty if the document has fewer than 3 usable headings."""
    text = _clean_lines(text, title); heads = detect(text, title); lines = text.split("\n"); out = []
    for j, (i, h) in enumerate(heads):
        end = heads[j + 1][0] if j + 1 < len(heads) else len(lines)
        body = _unwrap("\n".join(lines[i + 1:end])); sents = sentences(body)
        if len(sents) < 2: continue
        k = 5 if len(sents) > 18 else 4 if len(sents) > 9 else 3
        picks = _rank(sents, k) or sents[:2]
        out.append({"heading": pretty(h), "sentences": [{"text": s, "quote": s} for s in picks], "n": len(sents)})
    return out[:MAX_SECTIONS] if len(out) >= 3 else []
