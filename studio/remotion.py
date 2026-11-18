"""Bridge to the Remotion project in ./video (animated scenes rendered by headless Chrome). Optional: callers fall back to Pillow/ffmpeg."""
from __future__ import annotations
import json, math, re, shutil, subprocess
from pathlib import Path
from common import ROOT

VIDEO_DIR = ROOT / "video"
FPS = 30


def node_path() -> str | None:
    return shutil.which("node") or next((p for p in ("/opt/homebrew/bin/node", "/usr/local/bin/node") if Path(p).exists()), None)


def available() -> bool:
    return bool(node_path()) and (VIDEO_DIR / "node_modules" / "@remotion" / "renderer").exists() and any((VIDEO_DIR / "node_modules" / ".remotion").glob("chrome-headless-shell/**/chrome-headless-shell"))


def captions(text: str, frames: int, lead=6) -> list[dict]:
    sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+", text) if x.strip()] or [text]
    span = max(1, frames - lead - 20); tot = sum(len(x) for x in sents); out, t = [], lead
    for x in sents:
        d = max(12, round(span * len(x) / tot)); out.append({"text": x if len(x) < 170 else x[:167] + "…", "from": t, "to": t + d}); t += d
    return out


def frames_for(seconds: float | None) -> int: return int(math.ceil(((seconds or 4.0) + 0.9) * FPS))


def render(props: dict, workdir: Path, stills: Path | None = None, video: Path | None = None, scale=2 / 3, progress=lambda f, m="": None):
    pf = workdir / "props.json"; pf.write_text(json.dumps(props))
    cmd = [node_path(), "render.mjs", str(pf), "--publicDir", str(workdir)] + (["--stills", str(stills)] if stills else []) + (["--video", str(video), "--scale", str(scale)] if video else [])
    p = subprocess.Popen(cmd, cwd=VIDEO_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True); err = []
    for line in p.stdout:
        try: m = json.loads(line)
        except Exception: continue
        if m.get("stage") == "still": progress(0.3 + 0.6 * m["i"] / m["of"], f"rendering slide {m['i']}/{m['of']}")
        elif m.get("stage") == "video": progress(0.35 + 0.6 * m["progress"], f"rendering video {int(m['progress'] * 100)}%")
    err = p.stderr.read()
    if p.wait() != 0: raise RuntimeError("remotion render failed: " + (err if len(err) < 1400 else err[:900] + " … " + err[-450:]))
