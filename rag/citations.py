"""Citation parsing and construction. DOIs are only ever copied from stored metadata, never generated."""
from __future__ import annotations
import re

_MARK = re.compile(r"\[(\d+)\]")
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


_LEAD = re.compile(r"^\s*((?:\[\d+\]\s*)+)(.*)$", re.S)
_TRAIL = re.compile(r"([.!?])[ \t]+((?:\[\d+\][ \t]*)+)(?=[ \t]|$)")


def _normalize_markers(answer: str) -> str:
    """Put every marker at the end of the sentence it supports.
    - Line-leading markers ("[2][4] Sentence one. Two.") belong to that line's FIRST sentence.
    - Same-line markers after a period ("claim. [1]") belong to the sentence BEFORE them.
    A marker never crosses a newline."""
    # "[1, 2]" / "[1,2]" / "[1;2]" -> "[1][2]"
    answer = re.sub(r"\[(\d+(?:\s*[,;]\s*\d+)+)\]", lambda m: "".join(f"[{n}]" for n in re.findall(r"\d+", m.group(1))), answer)
    paras = []
    for para in re.split(r"\n+", answer.strip()):
        m = _LEAD.match(para)
        if m:
            marks, rest = m.group(1).strip(), m.group(2).strip()
            parts = _SENT.split(rest, 1)
            first = parts[0].rstrip(".!?") + " " + marks + "."
            para = first + (" " + parts[1] if len(parts) > 1 else "")
        para = _TRAIL.sub(lambda mm: " " + mm.group(2).strip() + mm.group(1), para)
        paras.append(para)
    return " ".join(paras)


def split_claims(answer: str) -> list[dict]:
    """Split an answer into sentences with their cited marker numbers."""
    out = []
    answer = _normalize_markers(answer)
    for s in _SENT.split(answer):
        s = s.strip()
        if not s:
            continue
        out.append({"text": s, "markers": [int(m) for m in _MARK.findall(s)], "is_interpretation": s.lower().startswith("interpretation")})
    return out


def build_citation_table(evidence) -> dict[int, dict]:
    tab = {}
    for n, e in enumerate(evidence, 1):
        m = e.metadata
        tab[n] = {"n": n, "doc_id": e.doc_id, "chunk_id": e.chunk_id, "title": e.title, "section": e.section,
                  "passage": e.passage, "char_start": e.char_start, "char_end": e.char_end,
                  "doi": m.get("doi"), "url": m.get("url") or (f"https://api.semanticscholar.org/CorpusID:{e.doc_id}" if m.get("source", "").startswith(("s2ag", "s2orc")) and e.doc_id.isdigit() and not e.chunk_id.count("/") else None),
                  "year": m.get("year"), "label": f"[{n}] {e.title or 'Untitled'} — {e.section or 'unlabeled'} — {e.passage[:140].strip()}…"}
    return tab
