from __future__ import annotations
import hashlib, time
from common import connect
from ingestion.pdf_parser import parse_pdf
from ingestion.metadata import detect_language, split_paragraphs, missing_metadata
from ingestion.chunking import chunk_document
from ingestion.deduplication import content_hash
from ingestion.weak_labels import primary_domain
from retrieval.hybrid import build_index

MAX_PDF_BYTES = 40 * 1024 * 1024


def add_pdf(owner: str, filename: str, data: bytes) -> dict:
    """Parse + chunk a user PDF into the user's PRIVATE partition. Never touches the shared corpus."""
    if not data[:5] == b"%PDF-": raise ValueError("not a PDF file")
    if len(data) > MAX_PDF_BYTES: raise ValueError("PDF too large")
    p = parse_pdf(data)
    doc_id = "u" + hashlib.sha1(data).hexdigest()[:16]
    con = connect()
    if con.execute("SELECT 1 FROM documents WHERE id=? AND owner=?", (doc_id, owner)).fetchone():
        return {"doc_id": doc_id, "duplicate": True, "title": p["title"]}
    dom = primary_domain(p["text"])
    row = dict(id=doc_id, owner=owner, title=p["title"] or filename, text=p["text"], source="upload", added=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
               created=None, version="upload", lang=detect_language(p["text"]), domain=dom, content_hash=content_hash(p["text"]), doi=p["doi"],
               authors=p["authors"], year=p["year"], has_full_text=1, origin="upload")
    row["meta_missing"] = ",".join(missing_metadata(row))
    con.execute(f"INSERT INTO documents({','.join(row)}) VALUES({','.join('?'*len(row))})", list(row.values()))
    chunks = chunk_document(doc_id, p["text"], "section", 512, 64, owner=owner)
    con.executemany("INSERT OR REPLACE INTO chunks(chunk_id,doc_id,owner,idx,section,char_start,char_end,n_tokens,text,domain,year,strategy) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    [(c.chunk_id, c.doc_id, owner, c.idx, c.section, c.char_start, c.char_end, c.n_tokens, c.text, dom, p["year"], c.strategy) for c in chunks])
    con.commit()
    return {"doc_id": doc_id, "title": row["title"], "chunks": len(chunks), "pages": p["n_pages"], "ocr_used": p["ocr_used"], "doi": p["doi"], "duplicate": False}


def upload_and_index(owner: str, files: list[tuple[str, bytes]], progress=None) -> dict:
    out = []
    for i, (fn, data) in enumerate(files):
        try: out.append({"file": fn, **add_pdf(owner, fn, data)})
        except Exception as e: out.append({"file": fn, "error": str(e)})
        if progress: progress(0.5 * (i + 1) / len(files), f"parsed {fn}")
    if any("chunks" in o for o in out):
        idx = build_index(owner=owner, progress=lambda f, m: progress and progress(0.5 + 0.5 * f, m))
        return {"files": out, "index": idx}
    return {"files": out, "index": None}
