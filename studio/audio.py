"""Two-host audio overview. Dialogue = the paper's own sentences arranged as Q&A (extractive, labelled as such);
speech synthesis = macOS `say` (offline) joined with ffmpeg."""
from __future__ import annotations
import subprocess, wave
from pathlib import Path

VOICES = {"A": "Samantha", "B": "Daniel"}
GAP_S = 0.35


ACKS = ["Okay.", "I see.", "Right.", "Go on.", "Mm-hm, and then?", "That's interesting."]
_SENT = __import__("re").compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])")


def _clean(s: str) -> str: return " ".join(s.split())


def dialogue(brief: dict) -> list[dict]:
    """Two-host walk through every section of each paper, in the paper's own words (complete sentences, nothing clipped).
    A host's long answer is split into short turns with a brief acknowledgement from the other host."""
    T: list[dict] = []; ack = [0]
    def say(spk, text, ref=None):
        if text.strip(): T.append({"speaker": spk, "text": _clean(text), **({"quote": ref} if ref else {})})
    def answer(items, empty):
        """Host B reads items (list of {text, quote}) in turns of up to 2 sentences; host A acknowledges between turns."""
        if not items: say("B", empty); return
        sents = [(x["text"], x["quote"]) for x in items]; groups = [sents[i:i + 2] for i in range(0, len(sents), 2)]
        for gi, g in enumerate(groups):
            if gi: say("A", ACKS[ack[0] % len(ACKS)]); ack[0] += 1
            say("B", " ".join(t for t, _ in g), g[0][1])
    say("A", "Welcome. In this overview we go through what the paper actually says, section by section, using its own sentences. Nothing here is added from outside the paper.")
    for p in brief["papers"]:
        say("A", f"This one is titled: {p['title']}." + (f" It was published in {p['year']}." if p["year"] else ""))
        if p.get("sections"):
            for si, sec in enumerate(p["sections"]):
                say("A", f"What does it say about {sec['heading']}?" if si else f"Let's start with the section called {sec['heading']}. What's in it?"); answer(sec["sentences"], "")
            continue
        say("A", "How does it open? What is it about?"); answer(p["abstract"], "I could not read an opening summary in the text.")
        say("A", "What question are the authors trying to answer?"); answer(p["research_question"], "The text does not state an explicit research question in the parts I could read.")
        say("A", "How did they go about it?"); answer(p["methodology"], "The method is not clearly stated in the sections I could extract.")
        say("A", "What did they find?"); answer(p["findings"], "No separate findings were detected beyond the opening summary.")
        nums = p["quantitative_results"] or p["numeric"]
        if nums: say("A", "Which concrete numbers should we remember?"); answer(nums, "")
        if p["conclusions"]: say("A", "And what do the authors conclude?"); answer(p["conclusions"], "")
        if p["limitations"]: say("A", "Are there any caveats?"); answer(p["limitations"], "")
        if p["future_work"]: say("A", "What comes next?"); answer(p["future_work"], "")
    if len(brief["papers"]) > 1:
        say("A", "How do these papers connect?")
        say("B", "They share these concepts: " + ", ".join(brief["shared_concepts"][:8]) + "." if brief["shared_concepts"] else "I did not find any concept that appears in every paper, so they cover different ground.")
    take = [x for p in brief["papers"] for x in ([sec["sentences"][0] for sec in (p["sections"][1:2] + p["sections"][-1:]) if sec["sentences"]] if p.get("sections") else (p["conclusions"][:1] or p["findings"][:1] or p["abstract"][-1:]))]
    if take: say("A", "So, the key takeaways?"); answer(take, "")
    say("A", "That's the overview. Check the quotes in the transcript before relying on any of it.")
    return T[:160]


def _run(cmd, **kw): subprocess.run(cmd, check=True, capture_output=True, **kw)


def tts(text: str, voice: str, out_wav: Path, rate=180):
    aiff = out_wav.with_suffix(".aiff")
    _run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff), "-f", "-"], input=text.encode())
    _run(["ffmpeg", "-y", "-i", str(aiff), "-ar", "24000", "-ac", "1", str(out_wav)]); aiff.unlink(missing_ok=True)


def _dur(p: Path) -> float:
    with wave.open(str(p)) as w: return w.getnframes() / w.getframerate()


def concat_wavs(wavs: list[Path], out: Path, listfile: Path):
    listfile.write_text("".join(f"file '{w}'\n" for w in wavs)); _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listfile), "-c:a", "aac", "-b:a", "96k", str(out)])


def synthesize(turns: list[dict], workdir: Path, out: Path, progress=lambda f, m="": None) -> list[dict]:
    workdir.mkdir(parents=True, exist_ok=True)
    sil = workdir / "gap.wav"; _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(GAP_S), str(sil)])
    wavs, t, timed = [], 0.0, []
    for i, turn in enumerate(turns):
        w = workdir / f"t{i:03d}.wav"; tts(turn["text"], VOICES[turn["speaker"]], w); d = _dur(w)
        timed.append({**turn, "start": round(t, 2), "end": round(t + d, 2)}); t += d + GAP_S; wavs += [w, sil]
        progress(0.1 + 0.8 * (i + 1) / len(turns), f"voicing {i + 1}/{len(turns)}")
    concat_wavs(wavs, out, workdir / "list.txt")
    for f in workdir.glob("t*.wav"): f.unlink()
    return timed
