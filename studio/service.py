from __future__ import annotations
import hashlib, json, re, shutil
from pathlib import Path
from common import OUT_DIR
from .brief import load_sources, build_brief
from extraction.findings import EXTRACT_VERSION
from .mindmap import mindmap
from .slides import slide_specs, render_all, to_pdf
from .audio import dialogue, synthesize
from .video import make_video
from . import remotion as rm
from .polish import polish_slides, polish_turns
from . import deck
from .pptx_export import build_pptx

KINDS = ("overview", "mindmap", "slides", "audio", "video")


def user_dir(user: str) -> Path: return OUT_DIR / "studio" / re.sub(r"\W", "", user)
VERSION = 6   # bump when generators change so cached outputs from older code are not served


def key_for(kind: str, ids: list[str], fluent: bool = False, ai_design: bool = False) -> str: return hashlib.sha1((f"v{VERSION}.{EXTRACT_VERSION}|{kind}|{int(fluent)}{int(ai_design)}|" + ",".join(sorted(ids))).encode()).hexdigest()[:12]


def _fluent_llm():
    from rag.synthesis import get_llm
    from models.nli import get_nli
    llm = get_llm("openai_compatible")
    try: llm.generate("Say OK.", max_tokens=5)
    except Exception as e: raise RuntimeError(f"Fluent narration needs the local LLM server ({llm.name}); it is not reachable: {type(e).__name__}. Start it with: .venv-llm/bin/mlx_lm.server --model mlx-community/Qwen2.5-3B-Instruct-4bit --port 8081") from None
    return llm, get_nli()


def generate(user: str, ids: list[str], owners: dict[str, str], kind: str, progress=lambda f, m="": None, fluent: bool = False, ai_design: bool = False) -> dict:
    fluent = fluent and kind in ("audio", "video"); ai_design = ai_design and kind == "slides"
    key = key_for(kind, ids, fluent, ai_design); d = user_dir(user) / key; meta = d / "result.json"
    if meta.exists(): return json.loads(meta.read_text()) | {"cached": True}
    d.mkdir(parents=True, exist_ok=True); progress(0.05, "reading sources")
    brief = build_brief(load_sources(ids, owners)); res = {"key": key, "kind": kind, "title": brief["title"], "note": brief["note"], "files": {}, "cached": False, "fluent": fluent}
    llm_nli, fell_back = None, False
    if fluent:
        try: llm_nli = _fluent_llm()
        except RuntimeError as e: fluent, fell_back, res["fluent"], res["fluent_note"] = False, True, False, str(e) + " Using the paper's own sentences instead."
    try:
        if kind == "overview": res["brief"] = brief
        elif kind == "mindmap": res["mindmap"] = mindmap(brief)
        elif kind == "slides":
            specs = slide_specs(brief); progress(0.1, "designing deck" + (" with AI" if ai_design else ""))
            dsg = deck.design(specs, brief["title"], ai=ai_design); specs = deck.apply(specs, dsg); th = dsg["theme"]; res["design"] = {"theme": th, "report": dsg["report"]}
            progress(0.2, "rendering slides"); res["renderer"] = "pillow"
            if rm.available():
                try:
                    rm.render({"slides": [{**x, "frames": 120, "captions": [], "audio": None} for x in specs], "fps": rm.FPS, "theme": {"bg": th["bg"], "accents": th["accents"]}}, d, stills=d, progress=progress); res["renderer"] = "remotion"
                except Exception: [p.unlink() for p in d.glob("slide_*.png")]
            if res["renderer"] == "pillow": render_all(specs, d)
            pngs = sorted(d.glob("slide_*.png")); to_pdf(pngs, d / "slides.pdf"); (d / "props.json").unlink(missing_ok=True)
            progress(0.95, "building PowerPoint"); build_pptx(specs, th, d / "deck.pptx", brief["title"])
            res["slides"] = specs; res["images"] = [p.name for p in pngs]; res["files"]["pdf"] = "slides.pdf"; res["files"]["pptx"] = "deck.pptx"
        elif kind == "audio":
            turns = dialogue(brief)
            if fluent: res["fluent_stats"] = polish_turns(turns, *llm_nli, progress=progress)
            res["transcript"] = synthesize(turns, d / "tmp", d / "overview.m4a", progress); res["files"]["audio"] = "overview.m4a"
            res["note"] += " The audio is a text-to-speech reading of those sentences arranged as Q&A, not a model-written explanation."
        elif kind == "video":
            res["slides"] = slide_specs(brief); th = deck.preset_for(brief["title"]); res["slides"] = deck.apply(res["slides"], deck.design(res["slides"], brief["title"]))
            if fluent: res["fluent_stats"] = polish_slides(res["slides"], *llm_nli, progress=progress)
            res["duration_s"], res["renderer"] = make_video(res["slides"], d / "tmp", d / "overview.mp4", progress, th); res["files"]["video"] = "overview.mp4"
        else: raise ValueError(kind)
    except Exception:
        shutil.rmtree(d, ignore_errors=True); raise
    shutil.rmtree(d / "tmp", ignore_errors=True); progress(0.98, "saving"); (None if fell_back else meta.write_text(json.dumps(res))); return res
