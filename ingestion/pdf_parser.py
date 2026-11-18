"""PDF -> normalized text + extracted metadata (PyMuPDF). OCR fallback only if tesseract is installed."""
from __future__ import annotations
import re, shutil
import pymupdf

from .metadata import normalize_text

DOI_RX = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+[^\s\"<>.,;)]", re.I)


def _strip_furniture(pages: list[str]) -> list[str]:
    """Drop running headers/footers (same line on many pages once digits are masked, e.g. 'Title … 12'), bare page numbers and figure captions,
    so they do not end up inside sentences, chunks or answers."""
    norm = lambda l: re.sub(r"\d+", "#", re.sub(r"\s+", " ", l.strip()))
    from collections import Counter
    cnt = Counter(norm(l) for t in pages for l in set(t.split("\n")) if l.strip())
    need = max(3, int(0.4 * len(pages)))
    out = []
    for t in pages:
        keep = [l for l in t.split("\n") if not (re.fullmatch(r"\s*\d{1,3}\s*", l) or (len(l.strip()) < 140 and cnt[norm(l)] >= need and len(pages) >= 4)
                                              or re.match(r"^\s*(?:Figure|Fig\.|Table)\s+\d+[:.]", l))]
        out.append("\n".join(keep))
    return out


def parse_pdf(data: bytes) -> dict:
    doc = pymupdf.open(stream=data, filetype="pdf")
    pages, ocr_used = [], False
    for p in doc:
        t = p.get_text("text")
        if len(t.strip()) < 30 and shutil.which("tesseract"):
            try:
                t = p.get_textpage_ocr(full=True).extractText(); ocr_used = True
            except Exception:
                pass
        pages.append(t)
    pages = _strip_furniture(pages)
    text = normalize_text("\n\n".join(pages))
    if len(text) < 200:
        raise ValueError("No extractable text (scanned PDF?). OCR " + ("failed." if shutil.which("tesseract") else "unavailable: install tesseract."))
    md = doc.metadata or {}
    title = (md.get("title") or "").strip() or _title_by_font(doc)
    doi = next(iter(DOI_RX.findall(text[:6000])), None)   # copied from the document itself, never generated
    year = None
    m = re.match(r"D:(\d{4})", md.get("creationDate") or "")
    if m: year = int(m.group(1))
    # prepend title so ingestion convention (title = first line) holds
    if title and not text.startswith(title):
        text = title + "\n\n" + text
    return {"title": title or None, "text": text, "doi": doi, "authors": (md.get("author") or None), "year": year,
            "n_pages": len(pages), "ocr_used": ocr_used}


def _title_by_font(doc) -> str | None:
    """Title = all first-page lines set in the largest font (covers often wrap the title over several lines), joined in reading order."""
    try:
        spans = []
        for b in doc[0].get_text("dict")["blocks"][:20]:
            for l in b.get("lines", []):
                t = " ".join(s["text"].strip() for s in l["spans"] if s["text"].strip())
                if t: spans.append((max(s["size"] for s in l["spans"]), t, l["bbox"][1]))
        spans = [x for x in spans if len(x[1]) > 3]
        if not spans: return None
        top = max(x[0] for x in spans); lines = [x for x in spans if x[0] >= top * 0.93]
        title = " ".join(x[1] for x in lines)[:200].strip()
        return title if len(title) > 8 else max(spans, key=lambda x: x[0])[1]
    except Exception:
        return None
