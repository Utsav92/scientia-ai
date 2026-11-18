from __future__ import annotations
import os, time, uuid, secrets
import bcrypt, jwt
from fastapi import Depends, HTTPException, Header
from common import connect, OUT_DIR

def _load_secret() -> str:
    """SCIENTIA_JWT_SECRET if set; otherwise a key generated once and stored (0600) so a server restart does not log everyone out."""
    if os.environ.get("SCIENTIA_JWT_SECRET"): return os.environ["SCIENTIA_JWT_SECRET"]
    f = OUT_DIR / ".jwt_secret"
    try:
        if f.exists() and f.read_text().strip(): return f.read_text().strip()
        f.parent.mkdir(parents=True, exist_ok=True); k = secrets.token_hex(32); f.write_text(k); f.chmod(0o600); return k
    except OSError:
        return secrets.token_hex(32)


SECRET = _load_secret()
ALGO, TTL = "HS256", 60 * 60 * 12


def register(email: str, password: str) -> str:
    con = connect()
    if con.execute("SELECT 1 FROM users WHERE email=?", (email.lower(),)).fetchone():
        raise HTTPException(409, "email already registered")
    uid = uuid.uuid4().hex
    con.execute("INSERT INTO users VALUES(?,?,?,?)", (uid, email.lower(), bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(), time.time()))
    con.commit(); return uid


def login(email: str, password: str) -> str:
    r = connect().execute("SELECT * FROM users WHERE email=?", (email.lower(),)).fetchone()
    if not r or not bcrypt.checkpw(password.encode(), r["pw_hash"].encode()):
        raise HTTPException(401, "invalid credentials")
    return jwt.encode({"sub": r["id"], "exp": time.time() + TTL}, SECRET, ALGO)


def current_user(authorization: str = Header(default="")) -> str:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer token")
    try:
        return jwt.decode(authorization[7:], SECRET, algorithms=[ALGO])["sub"]
    except jwt.PyJWTError:
        raise HTTPException(401, "invalid or expired token")


def audit(user: str, action: str, detail: str = ""):
    con = connect(); con.execute("INSERT INTO audit(ts,user,action,detail) VALUES(?,?,?,?)", (time.time(), user, action, detail[:500])); con.commit()
