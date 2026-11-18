"""Background jobs backed by SQLite (progress + result persisted; survives a page refresh)."""
from __future__ import annotations
import json, time, uuid, threading, traceback
from concurrent.futures import ThreadPoolExecutor
from common import connect

_POOL = ThreadPoolExecutor(max_workers=2)


def submit(owner: str, kind: str, fn, *args, max_retries: int = 1, **kw) -> str:
    jid = uuid.uuid4().hex[:12]
    con = connect()
    con.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)", (jid, owner, kind, "queued", 0.0, "", None, time.time(), time.time())); con.commit()

    def upd(status=None, progress=None, message=None, result=None):
        c = connect()
        c.execute("UPDATE jobs SET status=COALESCE(?,status), progress=COALESCE(?,progress), message=COALESCE(?,message), result=COALESCE(?,result), updated=? WHERE id=?",
                  (status, progress, message, json.dumps(result, default=str) if result is not None else None, time.time(), jid)); c.commit()

    def run():
        upd("running")
        for attempt in range(max_retries + 1):
            try:
                res = fn(*args, progress=lambda f, m="": upd(progress=min(f, 1.0), message=m), **kw)
                upd("done", 1.0, "", res); return
            except Exception as e:
                if attempt == max_retries:
                    upd("failed", message=f"{type(e).__name__}: {e}", result={"trace": traceback.format_exc()[-1500:]})
                else:
                    upd(message=f"retry {attempt + 1} after {type(e).__name__}")
    _POOL.submit(run)
    return jid


def get(jid: str, owner: str):
    r = connect().execute("SELECT * FROM jobs WHERE id=? AND owner=?", (jid, owner)).fetchone()
    if not r: return None
    d = dict(r); d["result"] = json.loads(d["result"]) if d["result"] else None
    return d
