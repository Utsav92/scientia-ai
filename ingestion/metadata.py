"""Text normalisation, section detection, title extraction, language detection."""
from __future__ import annotations
import re, unicodedata
from dataclasses import dataclass

# Only a conservative set of artefacts is removed; sci notation, formulas, citations are preserved.
_ZW = dict.fromkeys(map(ord, "​‌‍﻿­"), None)
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_MULTI_NL = re.compile(r"\n{3,}")


def normalize_text(t: str) -> str:
    # NFC (not NFKC): NFKC would rewrite sub/superscripts and ligature-based chemical/physics notation.
    t = unicodedata.normalize("NFC", t).translate(_ZW)
    t = _CTRL.sub("", t).replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"-\n(?=[a-z])", "", t)  # de-hyphenate line-break splits
    t = _MULTI_SPACE.sub(" ", t)
    return _MULTI_NL.sub("\n\n", t).strip()


SECTION_ALIASES = {
    "abstract": "abstract", "summary": "abstract",
    "introduction": "introduction", "intro": "introduction",
    "background": "background", "preliminaries": "background", "literature review": "related_work",
    "related work": "related_work", "related works": "related_work", "prior work": "related_work",
    "methods": "methodology", "method": "methodology", "methodology": "methodology",
    "materials and methods": "methodology", "experimental": "methodology", "experimental section": "methodology",
    "approach": "methodology", "model": "methodology", "experiments": "experiments", "experimental setup": "experiments",
    "experimental results": "results", "results": "results", "results and discussion": "results", "evaluation": "experiments",
    "discussion": "discussion", "limitations": "limitations", "limitation": "limitations",
    "conclusion": "conclusion", "conclusions": "conclusion", "concluding remarks": "conclusion",
    "future work": "conclusion", "conclusions and future work": "conclusion",
    # structured-abstract labels as found in PubMed-derived records
    "objective": "abstract", "objectives": "abstract", "purpose": "abstract", "aim": "abstract", "aims": "abstract",
}
_HEADING_STRIP = re.compile(r"^\s*(?:(?:\d+(?:\.\d+)*|[IVX]+)[.)]?\s+)?([A-Za-z][A-Za-z &,/\-]{1,60}?)[\s:.]*$")


def classify_heading(line: str) -> str | None:
    """Return a canonical section label if `line` is a recognised section heading, else None."""
    s = line.strip()
    if not s or len(s) > 70:
        return None
    m = _HEADING_STRIP.match(s)
    if not m:
        return None
    key = m.group(1).strip().lower()
    return SECTION_ALIASES.get(key)


@dataclass
class Paragraph:
    text: str
    start: int
    end: int
    section: str


def split_paragraphs(text: str) -> list[Paragraph]:
    """Split into paragraphs with char offsets into `text` and a rule-based section label.

    Heading lines are consumed as labels (not emitted); unknown pre-heading text is 'unlabeled'.
    peS2o v2 does not guarantee reliable section boundaries, so 'unlabeled' is a first-class value.
    """
    out: list[Paragraph] = []
    section = "unlabeled"
    for m in re.finditer(r"[^\n]+(?:\n(?!\n)[^\n]+)*", text):
        block, start = m.group(0), m.start()
        lines = block.split("\n")
        # A heading may be the first line of a block ("RESULTS\nWe found ...")
        h = classify_heading(lines[0]) if len(lines) >= 1 else None
        if h and len(lines) == 1:
            section = h
            continue
        if h:
            section = h
            offset = len(lines[0]) + 1
            out.append(Paragraph(block[offset:], start + offset, m.end(), section))
        else:
            out.append(Paragraph(block, start, m.end(), section))
    return out


def extract_title(text: str) -> str | None:
    first = text.split("\n", 1)[0].strip()
    if 8 <= len(first) <= 400:
        return first.strip("[]").rstrip(".") if first.startswith("[") else first
    return None


def detect_language(text: str) -> str | None:
    try:
        from langdetect import detect, DetectorFactory
        DetectorFactory.seed = 0
        return detect(text[:2000])
    except Exception:
        return None


def has_full_text(source: str | None, text: str, n_paragraphs: int) -> bool:
    """peS2o 's2orc' source = full text; 's2ag' = title+abstract. Verify with length instead of trusting blindly."""
    return bool(source and source.startswith("s2orc")) and len(text) > 4000


def missing_metadata(doc: dict) -> list[str]:
    return [k for k in ("title", "authors", "doi", "year") if not doc.get(k)]


def year_from(created: str | None) -> int | None:
    if created and re.match(r"^\d{4}", created):
        y = int(created[:4])
        return y if 1800 < y < 2100 else None
    return None
