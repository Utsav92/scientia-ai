"""Assemble the Launch film: speed-ramp the recorded clips, pull the REAL generated audio/video/slides, and write props.json + the public dir."""
import glob, json, shutil, subprocess, sys, wave
from pathlib import Path
import numpy as np

DM = Path(sys.argv[1]); PUB = DM / "pub"; FPS = 30
sys.path.insert(0, str(Path(__file__).parent)); import compose_clips
(PUB / "clips").mkdir(parents=True, exist_ok=True); (PUB / "slides").mkdir(exist_ok=True)
sh = lambda *a: subprocess.run(a, check=True, capture_output=True)

# 1. clips -> mp4 (waiting periods fast-forwarded)
dur = {}
for c in sorted((DM / "clips").iterdir()):
    if (c / "index.json").exists():
        out = PUB / "clips" / f"{c.name}.mp4"; dur[c.name] = compose_clips.build(c, out); print("clip", c.name, dur[c.name], "s")

# 2. real generated media from the demo backend's output dir
res = {}
for p in glob.glob(str(DM / "out/studio/*/*/result.json")):
    r = json.load(open(p)); r["_dir"] = str(Path(p).parent); res[r["kind"]] = r
AUDIO_S = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
a = res["audio"]; sh("ffmpeg", "-y", "-i", f"{a['_dir']}/overview.m4a", "-t", str(AUDIO_S), "-af", "afade=t=out:st=" + str(AUDIO_S - 1.2) + ":d=1.2", "-c:a", "aac", "-b:a", "192k", str(PUB / "audio_excerpt.m4a"))
sh("ffmpeg", "-y", "-i", str(PUB / "audio_excerpt.m4a"), "-ac", "1", "-ar", "16000", str(DM / "ex.wav"))
w = wave.open(str(DM / "ex.wav")); x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768; sr = w.getframerate(); hop = sr // FPS
rms = np.array([np.sqrt(np.mean(x[i:i + hop] ** 2)) for i in range(0, len(x) - hop, hop)]); env = np.clip(rms / (np.percentile(rms, 97) + 1e-9), 0, 1)
env = np.convolve(env, np.ones(3) / 3, mode="same"); turns = [{"speaker": t["speaker"], "text": t["text"], "start": t["start"], "end": min(t["end"], AUDIO_S)} for t in a["transcript"] if t["start"] < AUDIO_S - 1]
audio_frames = int(AUDIO_S * FPS) + 30

sl = res["slides"]; names = [f"slide_{i:02d}.png" for i in (1, 3, 5, 8, 11, 14, len(sl["slides"]))]
names = [n for n in names if (Path(sl["_dir"]) / n).exists()][:7]
for n in names: shutil.copy(Path(sl["_dir"]) / n, PUB / "slides" / n)
v = res["video"]; shutil.copy(f"{v['_dir']}/overview.mp4", PUB / "video_real.mp4")
VID_S = float(sys.argv[3]) if len(sys.argv) > 3 else 14.0

# 3. timeline
C = lambda name, head, sub, pill, zooms, accent, card=66: {"type": "clip", "clip": f"{name}.mp4", "frames": card + int(dur[name] * FPS) + 24, "head": head, "sub": sub, "pill": pill, "zooms": zooms, "cardFrames": card, "accent": accent}
plan = json.load(open(Path(__file__).parent / "plan.json"))
scenes = [{"type": "intro", "frames": 200}]
for key in ("upload", "ask", "mindmap"):
    p = plan[key]; scenes.append(C(key, p["head"], p["sub"], p["pill"], p["zooms"], p["accent"]))
p = plan["audio"]; scenes.append(C("audio", p["head"], p["sub"], p["pill"], p["zooms"], p["accent"]))
scenes.append({"type": "audio", "frames": audio_frames, "file": "audio_excerpt.m4a", "env": [round(float(e), 3) for e in env], "turns": turns, "head": plan["audio"]["real_head"]})
p = plan["slides"]; scenes.append(C("slides", p["head"], p["sub"], p["pill"], p["zooms"], p["accent"]))
scenes.append({"type": "wall", "frames": 210, "slides": names, "head": plan["slides"]["wall_head"], "sub": plan["slides"]["wall_sub"]})
p = plan["video"]; scenes.append(C("video", p["head"], p["sub"], p["pill"], p["zooms"], p["accent"]))
scenes.append({"type": "video", "frames": 60 + int(VID_S * FPS) + 40, "file": "video_real.mp4", "head": plan["video"]["real_head"], "sub": plan["video"]["real_sub"], "from": 0})
scenes.append({"type": "outro", "frames": 330})
# duck the music under real audio/video playback
duck, at = [], 0
for s in scenes:
    if s["type"] == "audio": duck.append([at + 24, at + 24 + int(AUDIO_S * FPS)])
    if s["type"] == "video": duck.append([at + 60, at + 60 + int(VID_S * FPS)])
    at += s["frames"]
shutil.copy(DM / "music.mp3", PUB / "music.mp3")
json.dump({"scenes": scenes, "music": "music.mp3", "duck": duck}, open(DM / "props.json", "w"))
print("total", at / FPS, "s;", len(scenes), "scenes;", "duck", duck)
