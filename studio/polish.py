"""Optional fluent narration: a local LLM rewrites *narration only* (never slide text or quotes), and every rewrite must pass
deterministic grounding checks against its own source sentences or it is discarded in favour of the verbatim text.
Checks (a baseline, not proof): no new numbers; mostly source vocabulary; no NLI contradiction against any source sentence."""
from __future__ import annotations
import re

_NUM = re.compile(r"\d+(?:\.\d+)?")
_STOP = set("about after again against also because before being between could during each either every first from further having however "
            "itself their there these they this those through under using very where which while whose would should other paper study studies".split())
_SPLIT = re.compile(r"(?<=[.!?])\s+")
MAX_UNGROUNDED = 0.35


def _vocab(t: str) -> set[str]: return {w[:6] for w in re.findall(r"[a-z]{5,}", t.lower()) if w not in _STOP}


def check(out: str, source: str, nli=None) -> tuple[bool, str]:
    if not out.strip() or len(out) > max(700, int(len(source) * 1.4)): return False, "empty or too long"
    if set(_NUM.findall(out)) - set(_NUM.findall(source)): return False, "introduces a number not in the source"
    ow, sw = _vocab(out), _vocab(source)
    if ow and len(ow - sw) / len(ow) > MAX_UNGROUNDED: return False, "too much vocabulary not in the source"
    if nli is not None:
        src = [s for s in _SPLIT.split(source) if len(s) > 20][:10]; outs = [s for s in _SPLIT.split(out) if len(s) > 15][:4]
        if src and outs:
            pairs = [(a, b) for a in src for b in outs]
            p = nli.probs([a for a, _ in pairs], [b for _, b in pairs])
            if float(p[:, 0].max()) > 0.7: return False, "contradicts a source sentence"
    return True, ""


def _clean(t: str) -> str:
    t = re.sub(r"[*_`#>]+", "", t).replace("\n", " ").strip().strip('"“”')
    return re.sub(r"\s+", " ", t)


RULES = ("Use ONLY facts stated in the source. Do not add numbers, names, causes, comparisons or conclusions that the source does not state. "
         "Plain spoken English, no lists, no markdown. Output only the spoken text.")


def polish(source: str, mode: str, llm, nli=None, title: str = "") -> tuple[str, bool, str]:
    """Returns (text, accepted, reason). On any failure the original `source` text is returned unchanged."""
    task = (f"Write a clear spoken narration for a slide titled '{title}', explaining ALL of its points in plain language, in about as many sentences as the source has." if mode == "slide"
            else "Rewrite this as a natural spoken reply from a podcast co-host, keeping every fact; at most one short sentence longer than the source.")
    try: out = _clean(llm.generate(f"{task} {RULES}\n\nSource:\n{source}\n\nSpoken text:", max_tokens=320))
    except Exception as e: return source, False, f"llm error: {type(e).__name__}"
    ok, why = check(out, source, nli)
    return (out, True, "") if ok else (source, False, why)


def polish_slides(specs: list[dict], llm, nli=None, progress=lambda f, m="": None) -> dict:
    acc = tot = 0
    for i, s in enumerate(specs):
        if s["kind"] in ("title", "sources") or not s["bullets"]: continue
        src = " ".join(b["text"].rstrip(".") + "." for b in s["bullets"]); tot += 1
        txt, ok, _ = polish(src, "slide", llm, nli, s["title"])
        if ok: s["narration"] = f"{s['title']}. {txt}"; acc += 1
        s["narration_source"] = "llm" if ok else "extractive"; progress(0.05 + 0.2 * (i + 1) / len(specs), f"polishing narration {i + 1}/{len(specs)}")
    return {"accepted": acc, "total": tot}


def polish_turns(turns: list[dict], llm, nli=None, progress=lambda f, m="": None) -> dict:
    acc = tot = 0
    for i, t in enumerate(turns):
        if t["speaker"] != "B" or len(t["text"]) < 60: continue
        tot += 1; txt, ok, _ = polish(t["text"], "turn", llm, nli)
        if ok: t["text"] = txt; acc += 1
        t["narration_source"] = "llm" if ok else "extractive"; progress(0.05 + 0.2 * (i + 1) / len(turns), f"polishing dialogue {i + 1}/{len(turns)}")
    return {"accepted": acc, "total": tot}
