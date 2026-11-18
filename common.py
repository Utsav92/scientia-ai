"""Shared paths, config and device helpers."""
from __future__ import annotations
import os, sqlite3, time, functools
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("SCIENTIA_DATA_DIR", ROOT / "datasets" / "processed"))
OUT_DIR = Path(os.environ.get("SCIENTIA_OUT_DIR", ROOT / "outputs"))
DB_PATH = Path(os.environ.get("SCIENTIA_DB", DATA_DIR / "scientia.db"))


def load_config(name: str) -> dict:
    with open(ROOT / "configs" / f"{name}.yaml") as f:
        return yaml.safe_load(f)


@functools.lru_cache(maxsize=1)
def get_device() -> str:
    import torch
    if os.environ.get("SCIENTIA_DEVICE"):
        return os.environ["SCIENTIA_DEVICE"]
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    p = Path(db_path or DB_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    init_schema(con)
    return con


SCHEMA = """
CREATE TABLE IF NOT EXISTS documents(
  id TEXT NOT NULL, owner TEXT NOT NULL DEFAULT '',      -- '' = shared corpus, else user id (isolation)
  title TEXT, text TEXT NOT NULL, source TEXT, added TEXT, created TEXT, version TEXT,
  lang TEXT, domain TEXT, content_hash TEXT, doi TEXT, url TEXT, authors TEXT, year INTEGER,
  has_full_text INTEGER, meta_missing TEXT, origin TEXT DEFAULT 'pes2o',
  PRIMARY KEY(id, owner));
CREATE INDEX IF NOT EXISTS ix_doc_hash ON documents(content_hash);
CREATE TABLE IF NOT EXISTS chunks(
  chunk_id TEXT PRIMARY KEY, doc_id TEXT NOT NULL, owner TEXT NOT NULL DEFAULT '',
  idx INTEGER, section TEXT, char_start INTEGER, char_end INTEGER, n_tokens INTEGER,
  text TEXT NOT NULL, domain TEXT, year INTEGER, strategy TEXT);
CREATE INDEX IF NOT EXISTS ix_chunk_doc ON chunks(doc_id, owner);
CREATE TABLE IF NOT EXISTS errors(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, stage TEXT, ref TEXT, message TEXT);
CREATE TABLE IF NOT EXISTS extractions(
  doc_id TEXT NOT NULL, owner TEXT NOT NULL DEFAULT '', method TEXT NOT NULL,   -- 'rules' | 'llm:<name>'
  data TEXT NOT NULL, stats TEXT, ts REAL, PRIMARY KEY(doc_id, owner, method));
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, email TEXT UNIQUE, pw_hash TEXT, created REAL);
CREATE TABLE IF NOT EXISTS library(id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT, doc_id TEXT, folder TEXT, tags TEXT);
CREATE TABLE IF NOT EXISTS saved_searches(id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT, query TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, owner TEXT, kind TEXT, status TEXT, progress REAL, message TEXT, result TEXT, created REAL, updated REAL);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, user TEXT, action TEXT, detail TEXT);
"""


def init_schema(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)
    con.commit()


class Timer:
    def __enter__(self):
        self.t = time.perf_counter(); return self
    def __exit__(self, *a):
        self.dt = time.perf_counter() - self.t
