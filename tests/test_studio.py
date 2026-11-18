import time
from test_api import client, reg, make_pdf, PAPER  # noqa: F401  (fixtures)
from studio.mindmap import mindmap
from studio.slides import slide_specs
from studio.audio import dialogue

def q(t): return {"text": t, "quote": t}
P = {"id": "d1", "title": "A Study of Widgets", "year": 2024, "domain": "ai_cs", "abstract": [q("Widgets are studied here in depth.")],
     "research_question": [q("We investigate widget durability.")], "methodology": [q("We use a stress rig.")], "findings": [q("Widgets last 10 years.")],
     "quantitative_results": [], "conclusions": [], "numeric": [], "limitations": [], "future_work": [], "entities": ["widget", "stress rig"]}
B = {"title": "A Study of Widgets", "note": "n", "papers": [P], "shared_concepts": []}

def test_mindmap_is_a_tree_from_root_with_quotes_only_from_source():
    m = mindmap(B); ids = {n["id"] for n in m["nodes"]}
    assert "root" in ids and all(e["source"] in ids and e["target"] in ids for e in m["edges"]) and len(m["edges"]) == len(m["nodes"]) - 1
    assert {n["quote"] for n in m["nodes"] if n.get("quote")} <= {"Widgets are studied here in depth.", "We investigate widget durability.", "We use a stress rig.", "Widgets last 10 years."}

def test_slides_skip_missing_sections_and_have_narration():
    s = slide_specs(B); titles = [x["title"] for x in s]
    assert titles[0] == "A Study of Widgets" and "Results" not in titles and "Key findings" in titles and titles[-1] == "Sources"
    assert all(x["narration"] for x in s)

def test_dialogue_is_honest_about_missing_info_and_bounded():
    t = dialogue({**B, "papers": [{**P, "research_question": [], "findings": []}]})
    txt = " ".join(x["text"] for x in t)
    assert "does not state an explicit research question" in txt and "No separate findings" in txt and len(t) <= 160
    assert {x["speaker"] for x in t} == {"A", "B"}

def test_studio_api_generate_serve_and_isolation(client):
    ha, hb = reg(client, "s1@x.org"), reg(client, "s2@x.org")
    r = client.post("/api/documents/upload", headers=ha, files=[("files", ("p.pdf", make_pdf(PAPER), "application/pdf"))])
    for _ in range(120):
        j = client.get(f"/api/jobs/{r.json()['job_id']}", headers=ha).json()
        if j["status"] in ("done", "failed"): break
        time.sleep(1)
    pid = j["result"]["files"][0]["doc_id"]
    def run(h, kind, ids):
        rr = client.post("/api/studio/generate", headers=h, json={"paper_ids": ids, "kind": kind})
        if rr.status_code != 202: return rr, None
        for _ in range(180):
            jj = client.get(f"/api/jobs/{rr.json()['job_id']}", headers=h).json()
            if jj["status"] in ("done", "failed"): return rr, jj
            time.sleep(1)
    assert run(hb, "slides", [pid])[0].status_code == 404                     # other user's paper
    assert client.post("/api/studio/generate", headers=ha, json={"paper_ids": [pid], "kind": "bogus"}).status_code == 422
    _, jj = run(ha, "slides", [pid]); assert jj["status"] == "done", jj
    res = jj["result"]; assert res["slides"] and res["files"]["pdf"] == "slides.pdf"
    assert res["images"] and client.get(f"/api/studio/file/{res['key']}/{res['images'][0]}", headers=ha).headers["content-type"] == "image/png"
    assert client.get(f"/api/studio/file/{res['key']}/{res['images'][0]}", headers=hb).status_code == 404
    f = client.get(f"/api/studio/file/{res['key']}/slides.pdf", headers=ha)
    assert f.status_code == 200 and f.content[:4] == b"%PDF"
    assert client.get(f"/api/studio/file/{res['key']}/slides.pdf", headers=hb).status_code == 404   # other user's output
    assert client.get(f"/api/studio/file/{res['key']}/../../x", headers=ha).status_code in (404, 422)
    _, mj = run(ha, "mindmap", [pid]); assert mj["status"] == "done" and mj["result"]["mindmap"]["nodes"]
    # chat scoped to the selected paper only
    a = client.post("/api/research/ask", headers=ha, json={"question": "What responsivity was reached?", "scope": "private", "paper_ids": [pid], "k": 3, "verify": False})
    assert a.status_code == 200 and all(c["doc_id"] == pid for c in a.json()["citations"].values())


def test_stats_extraction_keeps_compound_units_and_dedupes():
    from studio.slides import extract_stats
    s = extract_stats([q("Capacity was 390 mg/g and 365 mg/g."), q("Efficiency rose by 23% overall."), q("No numbers here at all.")])
    assert [x["display"] for x in s] == ["390 mg/g", "23%"] and s[1]["unit"] == "%" and s[0]["decimals"] == 0


def test_slide_kinds_are_visual_and_fall_back_when_data_missing():
    B2 = {**B, "papers": [{**P, "quantitative_results": [q("It reached 12.5% accuracy.")], "numeric": [q("It reached 12.5% accuracy.")], "conclusions": [q("We conclude it works.")],
                           "limitations": [q("Small sample.")], "future_work": [q("Scale up.")], "entities": ["a", "b", "c"]}]}
    kinds = [s["kind"] for s in slide_specs(B2)]
    assert kinds[0] == "title" and {"quote", "steps", "cards", "stats", "split", "concepts", "sources"} <= set(kinds)
    assert "stats" not in [s["kind"] for s in slide_specs(B)] and "concepts" not in [s["kind"] for s in slide_specs(B)]   # no numbers / <3 concepts -> no empty visuals
    assert all(s["bullets"] is not None and s["narration"] for s in slide_specs(B2))


LONG = [q(f"Finding number {i} is a complete sentence about widget durability that is deliberately long enough to need real space on a slide, with detail {i}.") for i in range(7)]


def test_slides_never_truncate_text_and_split_long_sections():
    B3 = {**B, "papers": [{**P, "findings": LONG, "abstract": [q("Opening sentence one is here."), q("Opening sentence two is here."), q("Opening sentence three is here."), q("Opening sentence four is here.")]}]}
    S = slide_specs(B3); texts = [b["text"] for s in S for b in s["bullets"]]
    assert not any("…" in t for t in texts + [s["title"] for s in S])                       # no ellipsis anywhere
    for l in LONG: assert l["text"] in texts                                                 # every finding appears in full
    assert [s["title"] for s in S if s["title"].startswith("Key findings")] == ["Key findings (1/3)", "Key findings (2/3)", "Key findings (3/3)"]
    assert [s["title"] for s in S if s["title"].startswith("Overview")] == ["Overview (1/2)", "Overview (2/2)"]
    multi = slide_specs({**B3, "papers": [B3["papers"][0], {**P, "id": "d2", "title": "A very long second paper title " * 3}]})
    assert all(len(s["title"]) < 40 for s in multi[1:-1]) and any(s.get("kicker", "").startswith("A very long second") for s in multi)   # paper title is a kicker, not in the heading


def test_mindmap_has_every_section_with_full_untruncated_leaves():
    B4 = {**B, "papers": [{**P, "findings": LONG[:2], "quantitative_results": [q("Accuracy rose to 91.5% on the benchmark under all tested conditions in the study.")],
                           "conclusions": [q("We conclude widgets are durable.")], "limitations": [q("Only one rig was tested.")], "future_work": [q("Test more rigs.")]}]}
    m = mindmap(B4); labels = {n["label"] for n in m["nodes"]}
    assert {"Summary", "Results", "Findings", "Conclusions", "Limitations", "Future work"} <= labels
    assert LONG[0]["text"] in labels and "Accuracy rose to 91.5% on the benchmark under all tested conditions in the study." in labels and not any("…" in l for l in labels)


def test_dialogue_reads_every_finding_in_full():
    t = dialogue({**B, "papers": [{**P, "findings": LONG[:5]}]}); txt = " ".join(x["text"] for x in t)
    assert all(l["text"] in txt for l in LONG[:5]) and "What do the authors conclude" not in txt   # conclusions only asked when present


def test_captions_cover_audio_in_order_without_overlap():
    from studio.remotion import captions
    c = captions("First sentence here. Second one follows! And a third?", 300)
    assert len(c) == 3 and all(a["to"] <= b["from"] for a, b in zip(c, c[1:])) and c[-1]["to"] <= 300 and c[0]["from"] >= 0


class _LLM:
    def __init__(self, out): self.out = out
    def generate(self, prompt, max_tokens=0): return self.out


def test_polish_accepts_grounded_rewrite_and_rejects_invented_facts():
    from studio.polish import polish
    src = "The photodetector achieves a dissymmetry factor of 0.35 under 450 nm illumination."
    t, ok, _ = polish(src, "turn", _LLM("So the photodetector reaches a dissymmetry factor of 0.35 under 450 nm illumination."))
    assert ok and "0.35" in t
    t, ok, why = polish(src, "turn", _LLM("It reaches a dissymmetry factor of 0.52 under 450 nm illumination."))
    assert not ok and t == src and "number" in why                                       # invented number -> verbatim kept
    t, ok, why = polish(src, "turn", _LLM("Revolutionary quantum computing breakthroughs transform telecommunications infrastructure globally."))
    assert not ok and t == src and "vocabulary" in why                                   # hallucinated content -> verbatim kept


def test_polish_survives_llm_failure_and_contradiction_guard():
    import numpy as np
    from studio.polish import polish, check
    class Boom:
        def generate(self, *a, **k): raise ConnectionError("down")
    t, ok, why = polish("Some source sentence about widgets here.", "turn", Boom()); assert not ok and t.startswith("Some source") and "llm error" in why
    class Contra:
        def probs(self, p, h): return np.array([[0.95, 0.02, 0.03]] * len(p))
    assert check("Widgets last ten years in testing.", "Widgets last 10 years in testing here today.", Contra())[1] == "contradicts a source sentence"


def _specs():
    B2 = {**B, "papers": [{**P, "quantitative_results": [q("It reached 12.5% accuracy.")], "limitations": [q("Small sample.")], "future_work": [q("Scale up.")], "entities": ["a", "b", "c"]}]}
    return slide_specs(B2), B2["title"]


def _client(reply):
    import httpx, json
    def h(request):
        body = {"content": [{"type": "text", "text": reply}]} if "anthropic" in str(request.url) else {"choices": [{"message": {"content": reply}}]}
        return httpx.Response(200, json=body)
    return httpx.Client(transport=httpx.MockTransport(h))


def test_ai_design_accepts_grounded_and_rejects_invented(monkeypatch):
    import json
    from studio import deck
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    specs, title = _specs(); i = next(n for n, s in enumerate(specs) if s["kind"] == "cards")
    good = {"theme": {"name": "Deep", "bg": "#05070d", "surface": "#121826", "text": "#f8fafc", "muted": "#a1a1aa", "accents": ["#22d3ee", "#a78bfa", "#facc15"], "heading_font": "Georgia", "body_font": "Calibri"},
            "slides": [{"index": i, "layout": "quote", "headline": "Widgets last ten years", "icon": "🔧", "notes": "Widgets last 10 years in the study."},
                       {"index": i + 1, "layout": "cards", "headline": "Revenue grew 400 percent", "icon": "x", "notes": "Quantum blockchain synergies unlocked."}]}
    d = deck.design(specs, title, ai=True, client=_client(json.dumps(good)))
    assert d["theme"]["name"] == "Deep" and d["slides"][i]["layout"] == "quote" and d["slides"][i]["headline"] == "Widgets last ten years" and d["slides"][i]["icon"] == "🔧"
    j = i + 1; assert d["slides"][j]["headline"] == specs[j]["title"] and d["slides"][j]["notes"] == specs[j]["narration"]   # invented headline/notes replaced by defaults
    assert any("slide" in r for r in d["report"]["rejected"])


def test_ai_design_rejects_bad_theme_bad_json_and_requires_key(monkeypatch):
    import json, pytest
    from studio import deck
    specs, title = _specs()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False); monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="API_KEY"): deck.design(specs, title, ai=True)
    monkeypatch.setenv("OPENAI_API_KEY", "t")
    light = {"theme": {"name": "x", "bg": "#ffffff", "surface": "#eeeeee", "text": "#111111", "muted": "#333333", "accents": ["#ff0000"] * 3, "heading_font": "Calibri", "body_font": "Calibri"}, "slides": []}
    d = deck.design(specs, title, ai=True, client=_client(json.dumps(light)))
    assert d["theme"]["name"] == deck.preset_for(title)["name"] and any("theme" in r for r in d["report"]["rejected"])
    d = deck.design(specs, title, ai=True, client=_client("sorry, I cannot do that"))
    assert "error" in d["report"] and d["theme"]["name"] == deck.preset_for(title)["name"]


def test_pptx_export_is_native_editable_in_bounds_with_notes(tmp_path):
    from pptx import Presentation
    from pptx.util import Emu
    from studio import deck
    from studio.pptx_export import build_pptx, SW, SH
    specs, title = _specs(); d = deck.design(specs, title); sp = deck.apply(specs, d); out = build_pptx(sp, d["theme"], tmp_path / "d.pptx", title)
    prs = Presentation(str(out)); assert len(prs.slides) == len(sp)
    for s in prs.slides:
        assert s.has_notes_slide and s.notes_slide.notes_text_frame.text.strip()
        for sh in s.shapes: assert -0.01 <= Emu(sh.left).inches and Emu(sh.left + sh.width).inches <= SW + 0.01 and -0.01 <= Emu(sh.top).inches and Emu(sh.top + sh.height).inches <= SH + 0.01
    assert any("Source quotes" in s.notes_slide.notes_text_frame.text for s in prs.slides)
    assert not any(sh.shape_type == 13 for s in prs.slides for sh in s.shapes)   # no flattened pictures: text stays editable


REPORT = ("A Plan for Lunar Presence\n\nA Plan for Lunar Presence      1\n\nOVERVIEW\nThe Moon is the gateway to the solar system and a world that humans have touched only a few times. Over the next decade\nthe program will lay the foundation for a sustained presence on the surface. This will cost 28 billion dollars over five years.\n"
          "THE FIRST LANDINGS\nCrews will land near the south pole by 2024. The first landing will test systems that\nlater missions depend on. Robotic landers will deliver instruments before any crew arrives.\nA Plan for Lunar Presence      2\nA BASE CAMP\nA small base camp will host four crew for weeks at a time. The camp will include a habitat, a rover and a power system.\nIts goal is to prove that people can live and work on the Moon.\n"
          "FUTURE\nMars is the next destination. The Moon will serve as the training ground for that mission and for the technologies it requires.\n")


def test_structure_uses_the_documents_own_headings_and_complete_sentences():
    from studio.structure import sections, detect, pretty
    secs = sections(REPORT, "A Plan for Lunar Presence")
    assert [s["heading"] for s in secs] == ["Overview", "The First Landings", "A Base Camp", "Future"]
    allt = " ".join(x["text"] for s in secs for x in s["sentences"])
    assert "A Plan for Lunar Presence" not in allt and "Over the next decade the program" in allt        # running header removed, wrapped line rejoined
    assert all(x["text"][0].isupper() and x["text"][-1] in ".!?" for s in secs for x in s["sentences"])   # no fragments
    assert pretty("NASA’S THREE DOMAIN STRATEGY") == "NASA’s Three Domain Strategy" and pretty("1. Introduction") == "Introduction"
    assert sections("Just one paragraph of plain prose without any headings at all, nothing to structure here.", "T") == []


def test_unwrap_joins_digit_and_function_word_continuations_but_not_headings():
    from extraction.findings import _unwrap
    t = _unwrap("We trained a gradient boosted model on\n1,240 measured materials from the literature.\nResults\nThe model was accurate.")
    assert "model on 1,240 measured" in t and "\nResults\n" in t


def test_mindmap_and_slides_follow_document_sections():
    from studio.structure import sections
    secs = sections(REPORT, "A Plan for Lunar Presence")
    Bs = {**B, "papers": [{**P, "sections": secs}]}
    labels = {n["label"] for n in mindmap(Bs)["nodes"]}; assert {"Overview", "The First Landings", "A Base Camp", "Future"} <= labels
    titles = [s["title"] for s in slide_specs(Bs)]; assert "The First Landings" in titles and "A Base Camp" in titles and titles[-1] == "Sources"
    txt = " ".join(x["text"] for x in dialogue(Bs)); assert "What does it say about The First Landings?" in txt
