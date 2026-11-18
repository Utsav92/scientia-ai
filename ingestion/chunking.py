"""Three chunking strategies. Token = regex word/punct unit (fast, deterministic, model-agnostic).
All chunks keep exact character offsets so the source passage is always text[char_start:char_end]."""
from __future__ import annotations
import re
from dataclasses import dataclass, asdict
from .metadata import split_paragraphs

_TOK = re.compile(r"\w+|[^\w\s]", re.UNICODE)
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])")


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    idx: int
    section: str
    char_start: int
    char_end: int
    n_tokens: int
    text: str
    strategy: str

    def to_dict(self): return asdict(self)


def count_tokens(s: str) -> int:
    return len(_TOK.findall(s))


def _mk(doc_id, idx, section, text, s, e, strategy, owner=""):
    seg = text[s:e]
    cid = f"{doc_id}:{idx}" if not owner else f"{owner}/{doc_id}:{idx}"
    return Chunk(cid, doc_id, idx, section, s, e, count_tokens(seg), seg, strategy)


def fixed_chunks(doc_id: str, text: str, max_tokens=512, overlap=64, owner="") -> list[Chunk]:
    toks = [(m.start(), m.end()) for m in _TOK.finditer(text)]
    if not toks:
        return []
    step = max(1, max_tokens - overlap)
    out, i = [], 0
    while i < len(toks):
        j = min(i + max_tokens, len(toks))
        out.append(_mk(doc_id, len(out), "unlabeled", text, toks[i][0], toks[j - 1][1], "fixed", owner))
        if j == len(toks):
            break
        i += step
    return out


def _sentence_spans(text: str, base: int, offset_text: str):
    spans, pos = [], 0
    for m in _SENT.finditer(offset_text):
        spans.append((base + pos, base + m.start())); pos = m.end()
    spans.append((base + pos, base + len(offset_text)))
    return [(a, b) for a, b in spans if b > a]


def _pack(doc_id, text, units, section, max_tokens, overlap, strategy, start_idx, owner):
    """units: list of (start,end) spans; greedily pack to <= max_tokens with sentence-level overlap."""
    out, cur, cur_tok = [], [], 0
    def flush():
        nonlocal cur, cur_tok
        if cur:
            out.append(_mk(doc_id, start_idx + len(out), section, text, cur[0][0], cur[-1][1], strategy, owner))
    for u in units:
        n = count_tokens(text[u[0]:u[1]])
        if cur and cur_tok + n > max_tokens:
            flush()
            keep, kt = [], 0
            for prev in reversed(cur):  # carry trailing sentences as overlap
                pn = count_tokens(text[prev[0]:prev[1]])
                if kt + pn > overlap: break
                keep.insert(0, prev); kt += pn
            cur, cur_tok = keep, kt
        cur.append(u); cur_tok += n
    flush()
    return out


def sentence_chunks(doc_id: str, text: str, max_tokens=512, overlap=64, owner="") -> list[Chunk]:
    units = []
    for p in split_paragraphs(text) or []:
        units += _sentence_spans(text, p.start, text[p.start:p.end])
    if not units:
        units = _sentence_spans(text, 0, text)
    return _pack(doc_id, text, units, "unlabeled", max_tokens, overlap, "sentence", 0, owner)


def section_chunks(doc_id: str, text: str, max_tokens=512, overlap=64, owner="") -> list[Chunk]:
    """Pack sentences within each rule-detected section; never merge across sections."""
    out: list[Chunk] = []
    paras = split_paragraphs(text)
    i = 0
    while i < len(paras):
        j = i
        while j < len(paras) and paras[j].section == paras[i].section:
            j += 1
        units = []
        for p in paras[i:j]:
            units += _sentence_spans(text, p.start, text[p.start:p.end])
        out += _pack(doc_id, text, units, paras[i].section, max_tokens, overlap, "section", len(out), owner)
        i = j
    return out


STRATEGIES = {"fixed": fixed_chunks, "sentence": sentence_chunks, "section": section_chunks}


def chunk_document(doc_id, text, strategy="section", max_tokens=512, overlap=64, owner="") -> list[Chunk]:
    return STRATEGIES[strategy](doc_id, text, max_tokens=max_tokens, overlap=overlap, owner=owner)
