"""Bounded, resumable streaming ingestion of peS2o (json.gz shards over HTTPS).

No `datasets` loading script is used and no remote code is executed: the repository ships plain
gzip-JSONL shards, which we stream and abort as soon as the document limit / quota is reached.
"""
from __future__ import annotations
import gzip, json, time, zlib, logging
from pathlib import Path
from typing import Iterator
import httpx
from pydantic import BaseModel, ValidationError, field_validator

from common import load_config, connect, OUT_DIR
from .metadata import normalize_text, extract_title, detect_language, split_paragraphs, has_full_text, year_from, missing_metadata
from .chunking import chunk_document
from .deduplication import content_hash, NearDupIndex
from .weak_labels import primary_domain

log = logging.getLogger("ingest")
LICENSE = {
    "dataset": "allenai/peS2o", "license": "ODC-By 1.0 (https://opendatacommons.org/licenses/by/1-0/)",
    "attribution": "Soldaini & Lo (2023), peS2o (Pretraining Efficiently on S2ORC) Dataset, Allen Institute for AI.",
    "notes": "Underlying papers (S2ORC) carry document-level licences; check them before redistributing full text.",
}


class Record(BaseModel):
    id: str
    text: str
    source: str | None = None
    added: str | None = None
    created: str | None = None
    version: str | None = None

    @field_validator("text")
    @classmethod
    def _nonempty(cls, v):
        if len(v.strip()) < 50:
            raise ValueError("text too short")
        return v


def shard_url(version: str, split: str, i: int, n: int, base: str) -> str:
    return f"{base}/{version}/{split}-{i:05d}-of-{n:05d}.json.gz"


def stream_lines(url: str, skip: int = 0, timeout: float = 60) -> Iterator[tuple[int, str]]:
    """Yield (line_no, raw_json_line) from a remote .json.gz without downloading the whole file."""
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    buf, n = b"", 0
    with httpx.stream("GET", url, follow_redirects=True, timeout=timeout) as r:
        r.raise_for_status()
        for chunk in r.iter_bytes(1 << 16):
            buf += d.decompress(chunk)
            *lines, buf = buf.split(b"\n")
            for ln in lines:
                n += 1
                if n > skip and ln.strip():
                    yield n, ln.decode("utf-8", "replace")


def ingest(limit: int, version="v2", split="train", shard=0, n_shards=20, quota_per_domain: int | None = None,
           db_path=None, resume=True, chunk_strategy="section", max_tokens=512, overlap=64,
           local_file: str | None = None, progress=None, language="en") -> dict:
    cfg = load_config("retrieval")
    base = cfg["ingest"]["base_url"]
    con = connect(db_path)
    ck_path = OUT_DIR / "reports" / f"ingest_checkpoint_{version}_{split}_{shard}.json"
    ck_path.parent.mkdir(parents=True, exist_ok=True)
    ck = json.loads(ck_path.read_text()) if (resume and ck_path.exists()) else {"lines": 0, "stored": 0}
    stats = {"seen": 0, "stored": 0, "invalid": 0, "exact_dup": 0, "near_dup": 0, "non_english": 0,
             "quota_skipped": 0, "errors": 0, "chunks": 0, "domains": {}, "started": time.time()}
    # rebuild dedup state from what is already stored (resume-safe)
    seen_ids = {r[0] for r in con.execute("SELECT id FROM documents WHERE owner=''")}
    seen_hash = {r[0] for r in con.execute("SELECT content_hash FROM documents WHERE owner=''")}
    nd = NearDupIndex()
    for r in con.execute("SELECT id, text FROM documents WHERE owner='' LIMIT 20000"):
        nd.check_and_add(r["id"], r["text"])
    for r in con.execute("SELECT domain, COUNT(*) c FROM documents WHERE owner='' GROUP BY domain"):
        stats["domains"][r["domain"]] = r["c"]
    stored_total = len(seen_ids)

    url = shard_url(version, split, shard, n_shards, base)
    log.info("streaming %s (resume from line %d, stored so far %d)", url, ck["lines"], stored_total)
    if local_file:
        def _it():
            with (gzip.open(local_file, "rt") if local_file.endswith(".gz") else open(local_file)) as f:
                for i, ln in enumerate(f, 1):
                    if i > ck["lines"] and ln.strip(): yield i, ln
        src = _it()
    else:
        src = stream_lines(url, skip=ck["lines"])
    last_line = ck["lines"]
    for line_no, raw in src:
        if stored_total >= limit:
            break
        last_line = line_no
        stats["seen"] += 1
        try:
            rec = Record(**{k: v for k, v in json.loads(raw).items() if k in Record.model_fields})
        except (ValidationError, json.JSONDecodeError, TypeError) as e:
            stats["invalid"] += 1
            con.execute("INSERT INTO errors(ts,stage,ref,message) VALUES(?,?,?,?)", (time.time(), "validate", f"line{line_no}", str(e)[:300]))
            continue
        try:
            text = normalize_text(rec.text)
            if rec.id in seen_ids:
                stats["exact_dup"] += 1; continue
            h = content_hash(text)
            if h in seen_hash:
                stats["exact_dup"] += 1; continue
            lang = detect_language(text)
            if language and lang and lang != language:
                stats["non_english"] += 1; continue
            dom = primary_domain(text)
            if quota_per_domain and stats["domains"].get(dom, 0) >= quota_per_domain:
                stats["quota_skipped"] += 1; continue
            if nd.check_and_add(rec.id, text):
                stats["near_dup"] += 1; continue
            paras = split_paragraphs(text)
            title = extract_title(text)
            row = dict(id=rec.id, owner="", title=title, text=text, source=rec.source, added=rec.added, created=rec.created,
                       version=rec.version, lang=lang, domain=dom, content_hash=h, year=year_from(rec.created),
                       has_full_text=int(has_full_text(rec.source, text, len(paras))), origin="pes2o")
            row["meta_missing"] = ",".join(missing_metadata(row))
            cols = ",".join(row); qs = ",".join("?" * len(row))
            con.execute(f"INSERT INTO documents({cols}) VALUES({qs})", list(row.values()))
            chunks = chunk_document(rec.id, text, chunk_strategy, max_tokens, overlap)
            con.executemany(
                "INSERT OR REPLACE INTO chunks(chunk_id,doc_id,owner,idx,section,char_start,char_end,n_tokens,text,domain,year,strategy) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                [(c.chunk_id, c.doc_id, "", c.idx, c.section, c.char_start, c.char_end, c.n_tokens, c.text, dom, row["year"], c.strategy) for c in chunks])
            seen_ids.add(rec.id); seen_hash.add(h)
            stored_total += 1; stats["stored"] += 1; stats["chunks"] += len(chunks)
            stats["domains"][dom] = stats["domains"].get(dom, 0) + 1
        except Exception as e:  # keep going; report at the end
            stats["errors"] += 1
            con.execute("INSERT INTO errors(ts,stage,ref,message) VALUES(?,?,?,?)", (time.time(), "process", rec.id, repr(e)[:300]))
        if stats["seen"] % 500 == 0:
            con.commit()
            ck_path.write_text(json.dumps({"lines": last_line, "stored": stored_total}))
            if progress: progress(stored_total / max(limit, 1), f"{stored_total}/{limit} docs")
            log.info("seen=%d stored=%d", stats["seen"], stored_total)
    con.commit()
    ck_path.write_text(json.dumps({"lines": last_line, "stored": stored_total}))
    stats["elapsed_s"] = round(time.time() - stats["started"], 1)
    stats["total_documents"] = stored_total
    report = {"url": url, "license": LICENSE, "stats": stats, "limit": limit,
              "errors_sample": [dict(r) for r in con.execute("SELECT stage,ref,message FROM errors ORDER BY id DESC LIMIT 20")]}
    (OUT_DIR / "reports" / f"ingest_report_{version}_{split}_{shard}.json").write_text(json.dumps(report, indent=2))
    (Path(__file__).resolve().parent.parent / "datasets" / "manifests" / "pes2o_license.json").write_text(json.dumps(LICENSE, indent=2))
    return report
