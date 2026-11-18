"""Video overview = rendered slides + synthesized narration, one segment per slide, joined with ffmpeg."""
from __future__ import annotations
from pathlib import Path
from .audio import tts, _run, _dur
from . import remotion as rm
from .slides import render_all


def make_video_pillow(specs: list[dict], workdir: Path, out: Path, progress=lambda f, m="": None) -> float:
    workdir.mkdir(parents=True, exist_ok=True)
    pngs = render_all(specs, workdir); segs, total = [], 0.0
    for i, (s, png) in enumerate(zip(specs, pngs)):
        wav = workdir / f"n{i:02d}.wav"; tts(s["narration"], "Samantha", wav); total += _dur(wav) + 0.8
        seg = workdir / f"seg{i:02d}.mp4"
        _run(["ffmpeg", "-y", "-loop", "1", "-framerate", "5", "-i", str(png), "-i", str(wav), "-af", "apad=pad_dur=0.8", "-c:v", "libx264", "-tune", "stillimage",
              "-pix_fmt", "yuv420p", "-r", "10", "-c:a", "aac", "-b:a", "96k", "-shortest", str(seg)])
        segs.append(seg); progress(0.1 + 0.8 * (i + 1) / len(specs), f"rendering slide {i + 1}/{len(specs)}")
    lst = workdir / "segs.txt"; lst.write_text("".join(f"file '{p}'\n" for p in segs))
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
    for f in list(workdir.glob("n*.wav")) + segs: f.unlink(missing_ok=True)
    return round(total, 1)


def make_video(specs: list[dict], workdir: Path, out: Path, progress=lambda f, m="": None, theme: dict | None = None) -> tuple[float, str]:
    """Animated Remotion render when available (graphics, transitions, captions); otherwise the plain slides+narration fallback."""
    if not rm.available(): return make_video_pillow(specs, workdir, out, progress), "pillow"
    workdir.mkdir(parents=True, exist_ok=True); slides = []
    for i, s in enumerate(specs):
        wav = workdir / f"n{i:02d}.wav"; tts(s["narration"], "Samantha", wav); fr = rm.frames_for(_dur(wav))
        slides.append({**s, "frames": fr, "audio": wav.name, "captions": rm.captions(s["narration"], fr)}); progress(0.05 + 0.25 * (i + 1) / len(specs), f"voicing {i + 1}/{len(specs)}")
    rm.render({"slides": slides, "fps": rm.FPS, **({"theme": {"bg": theme["bg"], "accents": theme["accents"]}} if theme else {})}, workdir, video=out, progress=progress)
    for f in workdir.glob("n*.wav"): f.unlink(missing_ok=True)
    return round(sum(x["frames"] for x in slides) / rm.FPS, 1), "remotion"
