"""Deck designer. An LLM (Claude via ANTHROPIC_API_KEY, else OpenAI via OPENAI_API_KEY) may choose the theme, per-slide layout,
takeaway headline, an icon and speaker notes. Body text, numbers and quotes always stay verbatim from the paper, and every model-written
string is checked against its slide's source text (no new numbers, mostly source vocabulary) or replaced by the plain default.
Without a key (or with ai=False) a deterministic designer picks a curated theme, so export never depends on an external service."""
from __future__ import annotations
import hashlib, json, os, re
import httpx
from .polish import check

FONTS = ["Calibri", "Georgia", "Arial", "Trebuchet MS", "Cambria"]
PRESETS = [
    {"name": "Midnight", "bg": "#0b0e14", "surface": "#161b26", "text": "#f1f5f9", "muted": "#94a3b8", "accents": ["#38bdf8", "#a78bfa", "#34d399", "#fbbf24"], "heading_font": "Calibri", "body_font": "Calibri"},
    {"name": "Aurora", "bg": "#0a1220", "surface": "#12233a", "text": "#ecfeff", "muted": "#94b8c9", "accents": ["#2dd4bf", "#60a5fa", "#a3e635", "#f472b6"], "heading_font": "Trebuchet MS", "body_font": "Calibri"},
    {"name": "Ember", "bg": "#150d12", "surface": "#26151d", "text": "#fff1f2", "muted": "#c4a3ae", "accents": ["#fb7185", "#fbbf24", "#f97316", "#c084fc"], "heading_font": "Georgia", "body_font": "Calibri"},
    {"name": "Forest", "bg": "#08130f", "surface": "#10231b", "text": "#ecfdf5", "muted": "#97b8aa", "accents": ["#34d399", "#a3e635", "#fbbf24", "#38bdf8"], "heading_font": "Cambria", "body_font": "Calibri"},
]
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
EQUIV = {"quote": {"quote", "cards"}, "cards": {"cards", "quote"}, "steps": {"steps", "cards"}, "stats": {"stats", "cards"}, "split": {"split", "cards"}, "concepts": {"concepts"}, "title": {"title"}, "sources": {"sources"}}


def _lum(h: str) -> float:
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]; c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True); return (la + 0.05) / (lb + 0.05)


def theme_problem(t: dict) -> str | None:
    """None if usable. Dark backgrounds only: the animated video/stills are dark, so PPTX and video must match."""
    try:
        cols = [t["bg"], t["surface"], t["text"], t["muted"], *t["accents"]]
        if not all(isinstance(c, str) and _HEX.match(c) for c in cols) or len(t["accents"]) < 3: return "invalid colours"
        if _lum(t["bg"]) > 0.12: return "background not dark"
        if contrast(t["text"], t["bg"]) < 7: return "text contrast too low"
        if contrast(t["muted"], t["bg"]) < 4.5: return "muted text contrast too low"
        if any(contrast(a, t["bg"]) < 3 for a in t["accents"]): return "accent contrast too low"
        if t.get("heading_font") not in FONTS or t.get("body_font") not in FONTS: return "unsupported font"
    except Exception: return "malformed theme"
    return None


def preset_for(title: str) -> dict: return dict(PRESETS[int(hashlib.md5(title.encode()).hexdigest(), 16) % len(PRESETS)])


def detect_provider() -> str | None:
    return "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "openai" if os.environ.get("OPENAI_API_KEY") else None


SYSTEM = ("You are a presentation designer for scientific papers. You choose design and wording of headlines and speaker notes only. "
          "You never change body text and never state any fact, number or name that is not in the supplied source sentences. Reply with JSON only.")


def _prompt(title: str, specs: list[dict]) -> str:
    rows = [{"index": i, "current_layout": s["kind"], "allowed_layouts": sorted(EQUIV[s["kind"]]), "title": s["title"],
             "source": [b["text"][:300] for b in (s.get("bullets") or [])[:3]]} for i, s in enumerate(specs) if s["kind"] not in ("title", "sources")]
    return ("Design a dark-themed deck for this paper summary.\nPAPER: " + title + "\nSLIDES:\n" + json.dumps(rows, ensure_ascii=False) +
            "\n\nReturn JSON exactly like: {\"theme\":{\"name\":str,\"bg\":\"#rrggbb\",\"surface\":\"#rrggbb\",\"text\":\"#rrggbb\",\"muted\":\"#rrggbb\",\"accents\":[\"#rrggbb\" x3-4],"
            "\"heading_font\":one of " + json.dumps(FONTS) + ",\"body_font\":one of " + json.dumps(FONTS) + "},\"slides\":[{\"index\":int,\"layout\":one of that slide's allowed_layouts,"
            "\"headline\":\"max 9 words, states the takeaway using only source facts\",\"icon\":\"one emoji\",\"notes\":\"2-4 sentences of speaker notes using only source facts\"}]}. "
            "The background must be very dark (near black) and text very light; choose a palette that suits the paper's field and mood.")


def _call(provider: str, prompt: str, client: httpx.Client | None = None) -> str:
    c = client or httpx.Client(timeout=120)
    if provider == "anthropic":
        r = c.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"},
                   json={"model": os.environ.get("SCIENTIA_DECK_MODEL", "claude-sonnet-5-5"), "max_tokens": 4000, "system": SYSTEM, "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status(); return "".join(b.get("text", "") for b in r.json()["content"])
    r = c.post("https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
               json={"model": os.environ.get("SCIENTIA_OPENAI_DECK_MODEL", "gpt-4o"), "response_format": {"type": "json_object"}, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]})
    r.raise_for_status(); return r.json()["choices"][0]["message"]["content"]


def _json(text: str) -> dict:
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b < a: raise ValueError("no JSON object in model reply")
    return json.loads(text[a:b + 1])


def _src(s: dict) -> str: return s["title"] + ". " + " ".join(b["text"] for b in (s.get("bullets") or []))


def design(specs: list[dict], title: str, ai: bool = False, provider: str | None = None, client: httpx.Client | None = None) -> dict:
    d = {"theme": preset_for(title), "slides": {}, "report": {"provider": None, "ai": False, "headlines": [0, 0], "notes": [0, 0], "rejected": []}}
    for i, s in enumerate(specs): d["slides"][i] = {"layout": s["kind"], "headline": s["title"], "icon": "", "notes": s.get("narration", "")}
    if not ai: return d
    provider = provider or detect_provider()
    if not provider: raise RuntimeError("AI design needs ANTHROPIC_API_KEY (Claude) or OPENAI_API_KEY set in the backend's environment.")
    rep = d["report"]; rep.update(provider=provider, ai=True)
    try: out = _json(_call(provider, _prompt(title, specs), client))
    except Exception as e: rep["error"] = f"{type(e).__name__}: {str(e)[:160]}"; return d
    t = out.get("theme") or {}; why = theme_problem(t) if isinstance(t, dict) else "missing theme"
    if why: rep["rejected"].append(f"theme: {why}")
    else: d["theme"] = {**t, "name": str(t.get("name", "Custom"))[:30]}
    for item in out.get("slides") or []:
        try: i = int(item["index"]); s = specs[i]
        except Exception: continue
        if s["kind"] in ("title", "sources"): continue
        slot, src = d["slides"][i], _src(s)
        if item.get("layout") in EQUIV[s["kind"]]: slot["layout"] = item["layout"]
        h = str(item.get("headline", "")).strip(); rep["headlines"][1] += 1
        if h and len(h.split()) <= 12 and check(h, src)[0]: slot["headline"] = h; rep["headlines"][0] += 1
        elif h: rep["rejected"].append(f"slide {i + 1} headline")
        n = str(item.get("notes", "")).strip(); rep["notes"][1] += 1
        if n and check(n, src)[0]: slot["notes"] = n; rep["notes"][0] += 1
        elif n: rep["rejected"].append(f"slide {i + 1} notes")
        ic = str(item.get("icon", "")).strip()
        if 0 < len(ic) <= 4 and not ic.isascii(): slot["icon"] = ic
    return d


def apply(specs: list[dict], d: dict) -> list[dict]:
    out = []
    for i, s in enumerate(specs):
        s = dict(s); slot = d["slides"][i]
        if slot["layout"] != s["kind"]: s["kind"] = slot["layout"]
        s["section"] = s["title"]; s["title"] = slot["headline"]; s["icon"] = slot["icon"]
        quotes = [b["quote"] for b in (s.get("bullets") or []) if b.get("quote")]
        s["notes"] = slot["notes"] + ("\n\nSource quotes (verbatim from the paper):\n" + "\n".join(f"- {q}" for q in quotes) if quotes else "")
        out.append(s)
    return out
