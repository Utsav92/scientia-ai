"""Slide specs (grounded bullets) + Pillow rendering to 1280x720 PNGs and a PDF."""
from __future__ import annotations
import re, textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
BG, FG, MUTED, ACC = (11, 14, 20), (230, 234, 242), (148, 163, 184), (56, 189, 248)
_FONTS = ["/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf"]


def font(size: int, bold=False):
    for f in _FONTS:
        try: return ImageFont.truetype(f, size, index=1 if bold and f.endswith(".ttc") else 0)
        except Exception: continue
    return ImageFont.load_default()


def _word_clip(s: str, n: int) -> str: return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + "…"


def _clip(s: str, n=230): return s if len(s) <= n else s[: n - 1].rstrip() + "…"


_NUM = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s?(%|percent|fold|×|x(?![a-z])|eV|nm|μm|GPa|MPa|mg(?:/[A-Za-z]+)?|ms|hours?|°C|K(?![a-z]))", re.I)


def extract_stats(items: list[dict], n=3) -> list[dict]:
    out, seen = [], set()
    for it in items:
        m = _NUM.search(it["text"])
        if not m or m.group(0) in seen: continue
        seen.add(m.group(0)); num = m.group(1)
        out.append({"display": m.group(0), "value": float(num), "decimals": len(num.split(".")[1]) if "." in num else 0, "unit": m.group(2).replace("percent", "%"), "label": it["text"], "quote": it["quote"]})
        if len(out) == n: break
    return out


def _items(xs) -> list[dict]: return [{"text": i["text"], "quote": i.get("quote")} for i in xs]


def _chunks(xs: list, n: int) -> list[list]: return [xs[i:i + n] for i in range(0, len(xs), n)] or []


def _part(title: str, i: int, n: int) -> str: return title if n == 1 else f"{title} ({i + 1}/{n})"


def slide_specs(brief: dict) -> list[dict]:
    """Slide specs with a visual `kind` + plain `bullets` (fallback renderer, accessibility). All text is complete sentences from the paper:
    nothing is truncated; long sections continue on further slides. Paper titles go in `kicker`, never crammed into the heading."""
    multi = len(brief["papers"]) > 1
    S = [{"kind": "title", "title": brief["title"], "bullets": [], "accent": 0,
          "subtitle": " · ".join(p["title"] for p in brief["papers"]) if multi else "A summary built from the paper's own text — expand any slide's quotes to verify"}]
    def add(kind, title, accent, items, kicker=None, **extra):
        S.append({"kind": kind, "title": title, "accent": accent, "bullets": items, "items": items, **({"kicker": kicker} if kicker else {}), **extra})
    shown: set[str] = set()   # a sentence is shown once across slides
    def fresh(xs): out = [i for i in _items(xs) if i["text"] not in shown]; shown.update(i["text"] for i in out); return out
    for pi, p in enumerate(brief["papers"]):
        kick = p["title"] if multi else None
        if p.get("sections"):   # structured document: one or two slides per real section
            for si, sec in enumerate(p["sections"]):
                its = fresh(sec["sentences"]); cs = _chunks(its, 3)
                for ci, c in enumerate(cs): add("quote" if len(c) <= 2 and (si + ci) % 2 == 0 else "cards", _part(sec["heading"], ci, len(cs)), pi + si, c, kick)
            stats = extract_stats(p["numeric"], 3)
            if stats: add("stats", "By the numbers", pi, [{"text": x["label"], "quote": x["quote"]} for x in stats], kick, stats=stats)
            continue
        ov = fresh(p["abstract"]); cs = _chunks(ov, 3)
        for i, c in enumerate(cs): add("quote", _part("Overview", i, len(cs)), pi, c, kick)
        rq, me = fresh(p["research_question"]), fresh(p["methodology"])
        steps = [{"label": "Question", "text": x["text"], "quote": x["quote"]} for x in rq[:1]] + [{"label": "Method", "text": x["text"], "quote": x["quote"]} for x in me[:2]]
        if len(steps) >= 2: add("steps", "Question → method", pi, [{"text": f"{x['label']}: {x['text']}", "quote": x["quote"]} for x in steps], kick, steps=steps)
        rest = rq[1:] + me[(2 if len(steps) >= 2 else 0):] if len(steps) >= 2 else rq + me
        for i, c in enumerate(_chunks(rest, 3)): add("cards", _part("Method & background", i, len(_chunks(rest, 3))), pi, c, kick)
        fd = fresh(p["findings"]); cs = _chunks(fd, 3)
        for i, c in enumerate(cs): add("cards", _part("Key findings", i, len(cs)), pi, c, kick)
        stats = extract_stats([x for x in p["numeric"]], 6)
        stat_texts = {x["label"] for x in stats}
        for i, c in enumerate(_chunks(stats, 3)): add("stats", _part("By the numbers", i, len(_chunks(stats, 3))), pi, [{"text": x["label"], "quote": x["quote"]} for x in c], kick, stats=c)
        shown.update(stat_texts)
        res = fresh(p["quantitative_results"]); cs = _chunks(res, 3)
        for i, c in enumerate(cs): add("cards", _part("Results", i, len(cs)), pi, c, kick)
        cn = fresh(p["conclusions"]); cs = _chunks(cn, 3)
        for i, c in enumerate(cs): add("quote", _part("Conclusions", i, len(cs)), pi, c, kick)
        lim, fut = fresh(p["limitations"]), fresh(p["future_work"])
        if lim and fut: add("split", "Limits & next steps", pi, lim + fut, kick, left=lim, right=fut, leftTitle="Limitations", rightTitle="Future work")
        elif lim or fut: add("cards", "Limitations" if lim else "Future work", pi, lim or fut, kick)
        if len(p["entities"]) >= 3: add("concepts", "Key concepts", pi, [{"text": ", ".join(p["entities"][:10]), "quote": None}], kick, concepts=p["entities"][:10], center=p["title"] if len(p["title"]) <= 40 else "Key concepts")
    if brief["shared_concepts"]: add("concepts", "Shared concepts", 2, [{"text": ", ".join(brief["shared_concepts"][:12]), "quote": None}], None, concepts=brief["shared_concepts"][:10], center="Shared across papers")
    take = []
    for p in brief["papers"]:
        if p.get("sections"): take += [sec["sentences"][0] for sec in (p["sections"][1:2] + p["sections"][-1:]) if sec["sentences"]] + p["sections"][0]["sentences"][:0]
        else: take += (p["conclusions"][:1] or p["findings"][:1] or p["abstract"][-1:])
    if len(S) > 4 and take: add("cards", "Key takeaways", 0, _items(take[:3]), None)
    add("sources", "Sources", 0, [{"text": f"{p['title']}" + (f" ({p['year']})" if p["year"] else ""), "quote": None} for p in brief["papers"][:6]])
    for i, s in enumerate(S, 1): s["narration"] = narration(s); s["n"] = i; s["total"] = len(S)
    return S


def narration(s: dict) -> str:
    if s["kind"] == "title": return f"{s['title']}. Here is an overview built from the paper's own text."
    return s["title"] + ". " + " ".join(b["text"].rstrip(".") + "." for b in s["bullets"])


def render(spec: dict, path: Path, n: int, total: int):
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 12, H], fill=ACC)
    if spec["kind"] == "title":
        y = 220
        for line in textwrap.wrap(spec["title"], 34)[:5]: d.text((90, y), line, font=font(58, True), fill=FG); y += 74
        d.text((90, y + 20), "Research overview · generated from source text", font=font(26), fill=MUTED)
    else:
        t = textwrap.wrap(spec["title"], 48)[:2]; y = 60
        for line in t: d.text((70, y), line, font=font(44, True), fill=FG); y += 56
        y += 24
        size = 32
        while True:  # shrink to fit
            f = font(size); lines = [(textwrap.wrap(b["text"], max(20, int(1100 / (size * 0.52)))) or [""]) for b in spec["bullets"]]
            if sum(len(l) for l in lines) * (size + 10) + len(lines) * 22 < H - y - 70 or size <= 18: break
            size -= 2
        for ls in lines:
            d.ellipse([72, y + size // 2 - 5, 82, y + size // 2 + 5], fill=ACC)
            for ln in ls: d.text((100, y), ln, font=f, fill=FG); y += size + 10
            y += 22
    d.text((W - 150, H - 44), f"{n} / {total}", font=font(22), fill=MUTED)
    im.save(path)


def render_all(specs: list[dict], outdir: Path) -> list[Path]:
    paths = []
    for i, s in enumerate(specs, 1): p = outdir / f"slide_{i:02d}.png"; render(s, p, i, len(specs)); paths.append(p)
    return paths


def to_pdf(pngs: list[Path], out: Path):
    ims = [Image.open(p).convert("RGB") for p in pngs]; ims[0].save(out, save_all=True, append_images=ims[1:], resolution=96)
