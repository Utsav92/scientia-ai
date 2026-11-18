"""Native, editable PowerPoint export (python-pptx shapes and text, no flattened images). 16:9, speaker notes carry the source quotes."""
from __future__ import annotations
import math
from pathlib import Path
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

SW, SH = 13.333, 7.5


def rgb(h: str) -> RGBColor: return RGBColor.from_string(h.lstrip("#").upper())


def fit(text: str, w: float, h: float, mx=26, mn=12) -> int:
    for pt in range(mx, mn - 1, -1):
        cpl = max(1, int(w * 72 / (pt * 0.54))); ps = text.split("\n"); lines = sum(max(1, math.ceil(len(p) / cpl)) for p in ps)
        if (lines * 1.3 + 0.5 * len(ps)) * pt / 72 <= h: return pt
    return mn


class Deck:
    def __init__(self, theme: dict):
        self.t = theme; self.prs = Presentation(); self.prs.slide_width, self.prs.slide_height = Inches(SW), Inches(SH)

    def new(self, notes: str = ""):
        s = self.prs.slides.add_slide(self.prs.slide_layouts[6]); s.background.fill.solid(); s.background.fill.fore_color.rgb = rgb(self.t["bg"])
        if notes: s.notes_slide.notes_text_frame.text = notes
        return s

    def text(self, s, x, y, w, h, txt, size, color=None, bold=False, font=None, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
        tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf = tb.text_frame; tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0; tf.vertical_anchor = anchor
        for k, para in enumerate(txt.split("\n")):
            p = tf.paragraphs[0] if k == 0 else tf.add_paragraph(); p.alignment = align; p.space_after = Pt(size * 0.5)
            r = p.add_run(); r.text = para; f = r.font; f.size = Pt(size); f.bold = bold; f.name = font or self.t["body_font"]; f.color.rgb = rgb(color or self.t["text"])
        return tb

    def shape(self, s, kind, x, y, w, h, fill=None, line=None, lw=1.5, radius=None):
        sh = s.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h)); sh.shadow.inherit = False
        if fill: sh.fill.solid(); sh.fill.fore_color.rgb = rgb(fill)
        else: sh.fill.background()
        if line: sh.line.color.rgb = rgb(line); sh.line.width = Pt(lw)
        else: sh.line.fill.background()
        if radius is not None and kind == MSO_SHAPE.ROUNDED_RECTANGLE: sh.adjustments[0] = radius
        return sh

    def accent(self, spec, k=0): a = self.t["accents"]; return a[(spec.get("accent", 0) + k) % len(a)]

    def heading(self, s, spec):
        a = self.accent(spec); self.shape(s, MSO_SHAPE.RECTANGLE, 0.5, 0.55, 0.1, 0.8, fill=a)
        x = 0.85
        if spec.get("icon"): self.text(s, 0.85, 0.55, 0.8, 0.8, spec["icon"], 30, anchor=MSO_ANCHOR.MIDDLE); x = 1.6
        self.text(s, x, 0.5, 10.6 - (x - 0.85), 0.9, spec["title"], fit(spec["title"], 10.6, 0.9, 34, 20), bold=True, font=self.t["heading_font"], anchor=MSO_ANCHOR.MIDDLE)
        self.text(s, 11.7, 0.65, 1.2, 0.4, f"{spec['n']} / {spec['total']}", 12, self.t["muted"], align=PP_ALIGN.RIGHT)
        if spec.get("kicker"): self.text(s, x, 0.18, 10.4, 0.34, spec["kicker"], 12 if len(spec["kicker"]) < 110 else 10, a, True)

    # ---- layouts -------------------------------------------------------------------------------------------------------------
    def title(self, spec):
        s = self.new(spec["notes"]); a = self.accent(spec)
        for r, k in ((1.2, 0), (1.9, 1), (2.6, 2)): self.shape(s, MSO_SHAPE.OVAL, 10.2 - r, 3.75 - r, 2 * r, 2 * r, line=self.accent(spec, k), lw=1.25 + k * 0.5)
        for ang, rr, k in ((0.4, 1.2, 0), (2.2, 1.9, 1), (4.0, 2.6, 2), (5.3, 1.9, 0)): self.shape(s, MSO_SHAPE.OVAL, 10.2 + rr * math.cos(ang) - 0.12, 3.75 + rr * math.sin(ang) - 0.12, 0.24, 0.24, fill=self.accent(spec, k))
        self.text(s, 0.9, 1.9, 7.4, 0.4, "RESEARCH OVERVIEW", 14, a, True)
        self.text(s, 0.9, 2.45, 7.6, 2.6, spec["title"], fit(spec["title"], 7.6, 2.6, 44, 24), bold=True, font=self.t["heading_font"])
        sub = spec.get("subtitle", "Built from the paper's own text"); self.text(s, 0.9, 5.3, 7.6, 1.5, sub, fit(sub, 7.6, 1.5, 16, 10), self.t["muted"])

    def quote(self, spec):
        s = self.new(spec["notes"]); self.heading(s, spec); a = self.accent(spec)
        self.text(s, 0.55, 1.3, 1.4, 2.0, "“", 110, a, True, "Georgia"); self.shape(s, MSO_SHAPE.RECTANGLE, 1.35, 2.05, 0.08, 4.4, fill=a)
        body = "\n".join(i["text"] for i in spec["items"][:3]); self.text(s, 1.75, 1.9, 10.6, 5.0, body, fit(body, 10.6, 5.0, 26, 12))

    def cards(self, spec):
        s = self.new(spec["notes"]); self.heading(s, spec); items = spec["items"][:3]; n = len(items); gap = 0.35; w = (12.33 - gap * (n - 1)) / n
        for i, it in enumerate(items):
            x = 0.5 + i * (w + gap); a = self.accent(spec, 0)
            self.shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, 1.9, w, 4.7, fill=self.t["surface"], line=a, lw=1, radius=0.06)
            self.shape(s, MSO_SHAPE.OVAL, x + 0.3, 2.2, 0.72, 0.72, fill=a); self.text(s, x + 0.3, 2.2, 0.72, 0.72, str(i + 1), 22, self.t["bg"], True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
            self.text(s, x + 0.3, 3.2, w - 0.6, 3.2, it["text"], fit(it["text"], w - 0.6, 3.2, 22, 12))

    def steps(self, spec):
        s = self.new(spec["notes"]); self.heading(s, spec); st = spec["steps"][:3]; n = len(st); arrow = 0.6; w = (12.33 - arrow * (n - 1)) / n
        for i, x_ in enumerate(st):
            x = 0.5 + i * (w + arrow); a = self.accent(spec)
            self.shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, 2.1, w, 3.8, fill=self.t["surface"], line=a if i == 0 else self.t["muted"], lw=2 if i == 0 else 1, radius=0.06)
            self.shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x + 0.3, 2.4, 1.5, 0.45, fill=a, radius=0.5); self.text(s, x + 0.3, 2.4, 1.5, 0.45, x_["label"].upper(), 12, self.t["bg"], True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
            self.text(s, x + 0.3, 3.1, w - 0.6, 2.6, x_["text"], fit(x_["text"], w - 0.6, 2.6, 22, 12))
            if i < n - 1: self.shape(s, MSO_SHAPE.RIGHT_ARROW, x + w + 0.08, 3.7, arrow - 0.16, 0.5, fill=a)

    def stats(self, spec):
        s = self.new(spec["notes"]); self.heading(s, spec); st = spec["stats"][:3]; n = len(st); gap = 0.35; w = (12.33 - gap * (n - 1)) / n
        for i, x_ in enumerate(st):
            x = 0.5 + i * (w + gap); a = self.accent(spec, i)
            self.shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, 1.9, w, 4.7, fill=self.t["surface"], line=a, lw=1, radius=0.06)
            self.text(s, x + 0.35, 2.2, w - 0.7, 1.3, f"{x_['value']:.{x_['decimals']}f}", fit(f"{x_['value']}", w - 0.7, 1.0, 66, 36), a, True, self.t["heading_font"], anchor=MSO_ANCHOR.MIDDLE)
            self.text(s, x + 0.35, 3.5, w - 0.7, 0.45, x_["unit"], 22, self.t["muted"], True)
            if x_["unit"] == "%":
                self.shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x + 0.35, 4.1, w - 0.7, 0.2, fill=self.t["bg"], radius=0.5)
                self.shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x + 0.35, 4.1, max(0.25, (w - 0.7) * min(100, x_["value"]) / 100), 0.2, fill=a, radius=0.5)
            self.text(s, x + 0.35, 4.55, w - 0.7, 1.9, x_["label"], fit(x_["label"], w - 0.7, 1.9, 16, 11), self.t["text"])

    def concepts(self, spec):
        s = self.new(spec["notes"]); self.heading(s, spec); c = spec["concepts"][:10]; cx, cy, rx, ry = SW / 2, 4.5, 4.4, 2.0; a = self.accent(spec)
        pts = [(cx + rx * math.cos(2 * math.pi * i / len(c) - math.pi / 2), cy + ry * math.sin(2 * math.pi * i / len(c) - math.pi / 2)) for i in range(len(c))]
        for px, py in pts:
            ln = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(cx), Inches(cy), Inches(px), Inches(py)); ln.line.color.rgb = rgb(a); ln.line.width = Pt(1.5)
        self.shape(s, MSO_SHAPE.OVAL, cx - 1.5, cy - 0.85, 3.0, 1.7, fill=a); self.text(s, cx - 1.3, cy - 0.85, 2.6, 1.7, spec.get("center", "Key concepts"), 16, self.t["bg"], True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        for (px, py), name in zip(pts, c):
            self.shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, px - 1.2, py - 0.3, 2.4, 0.6, fill=self.t["surface"], line=a, radius=0.5)
            self.text(s, px - 1.1, py - 0.3, 2.2, 0.6, name, fit(name, 2.2, 0.6, 14, 9), align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

    def split(self, spec):
        s = self.new(spec["notes"]); self.heading(s, spec)
        for k, (title, items, col) in enumerate(((spec.get("leftTitle", "Limitations"), spec.get("left", []), "#fb7185"), (spec.get("rightTitle", "Future work"), spec.get("right", []), self.accent(spec)))):
            x = 0.5 + k * 6.35; body = "\n".join(i["text"] for i in items[:3])
            self.shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, 1.9, 5.98, 4.7, fill=self.t["surface"], line=col, lw=1.5, radius=0.05)
            self.text(s, x + 0.4, 2.2, 5.2, 0.6, title, 24, col, True, self.t["heading_font"]); self.text(s, x + 0.4, 3.0, 5.2, 3.4, body, fit(body, 5.2, 3.4, 20, 12))

    def sources(self, spec):
        s = self.new(spec["notes"]); self.heading(s, spec)
        for i, it in enumerate(spec["items"][:6]):
            y = 1.9 + i * 0.8; a = self.accent(spec)
            self.shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, 0.7, y, 0.6, 0.6, fill=a, radius=0.2); self.text(s, 0.7, y, 0.6, 0.6, str(i + 1), 18, self.t["bg"], True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
            self.text(s, 1.6, y, 10.8, 0.6, it["text"], fit(it["text"], 10.8, 0.6, 20, 12), anchor=MSO_ANCHOR.MIDDLE)


def build_pptx(specs: list[dict], theme: dict, out: Path, title: str = "") -> Path:
    d = Deck(theme)
    for s in specs: getattr(d, s["kind"], d.cards)(s)
    d.prs.core_properties.title = title or specs[0]["title"]; d.prs.core_properties.author = "SCIENTIA AI"
    d.prs.save(str(out)); return out
