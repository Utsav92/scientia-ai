"""Turn a screencast clip (jpeg frames + timestamps + speed markers) into a 30fps mp4, fast-forwarding the marked waiting periods."""
import json, subprocess, sys
from pathlib import Path


def build(clip: Path, out: Path):
    idx = json.loads((clip / "index.json").read_text()); fr, sp, end = idx["frames"], idx["speeds"], idx["end"]
    k_at = lambda t: next((s["k"] for s in reversed(sp) if s["t"] <= t), 1)
    lines, total = [], 0.0
    for i, f in enumerate(fr):
        t0 = f["ts"]; t1 = fr[i + 1]["ts"] if i + 1 < len(fr) else max(t0 + 0.4, end)
        d, t = 0.0, t0
        for b in [s["t"] for s in sp if t0 < s["t"] < t1] + [t1]: d += (b - t) / k_at(t); t = b
        d = max(d, 1 / 60); total += d; lines.append(f"file 'frames/{f['f']}'\nduration {d:.4f}")
    lines.append(f"file 'frames/{fr[-1]['f']}'")
    (clip / "list.txt").write_text("\n".join(lines))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(clip / "list.txt"), "-vf", "fps=30,scale=2160:1350:flags=lanczos,format=yuv420p",
                    "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-r", "30", str(out)], check=True)
    return round(total, 2)


if __name__ == "__main__":
    work = Path(sys.argv[1]); res = {}
    for c in sorted((work / "clips").iterdir()):
        if (c / "index.json").exists(): res[c.name] = build(c, work / f"{c.name}.mp4"); print(c.name, res[c.name], "s")
    (work / "clip_durations.json").write_text(json.dumps(res))
