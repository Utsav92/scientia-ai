from __future__ import annotations
import hashlib

BRANCHES = [("abstract", "Summary"), ("research_question", "Research question"), ("methodology", "Methodology"), ("quantitative_results", "Results"),
            ("findings", "Findings"), ("conclusions", "Conclusions"), ("limitations", "Limitations"), ("future_work", "Future work")]


def mindmap(brief: dict) -> dict:
    """Tree: root -> (paper) -> section -> full-sentence leaves. Labels are never truncated; the UI sizes nodes to fit."""
    nodes = [{"id": "root", "kind": "root", "label": brief["title"]}]; edges = []
    def add(i, kind, label, parent, quote=None, **kw):
        nodes.append({"id": i, "kind": kind, "label": label, **({"quote": quote} if quote else {}), **kw}); edges.append({"source": parent, "target": i, "rel": "has", "kind": "extracted"})
    multi = len(brief["papers"]) > 1
    for p in brief["papers"]:
        pid = "p" + hashlib.md5(p["id"].encode()).hexdigest()[:6]
        if multi: add(pid, "paper", p["title"], "root", doc_id=p["id"], domain=p["domain"] or "other"); top = pid
        else: top = "root"
        used: set[str] = set()   # outside the Summary, a sentence is listed once
        if p.get("sections"):    # the document's own headings, in order
            for si, sec in enumerate(p["sections"]):
                bid = f"{pid}-s{si}"; add(bid, "branch", sec["heading"], top)
                for n, it in enumerate(sec["sentences"]): add(f"{bid}-{n}", "leaf", it["text"], bid, it["quote"])
        else:
          for key, label in BRANCHES:
              items = [it for it in p[key] if key == "abstract" or it["text"] not in used]
              if not items: continue
              bid = f"{pid}-{key}"; add(bid, "branch", label, top)
              for n, it in enumerate(items): used.add(it["text"]); add(f"{bid}-{n}", "leaf", it["text"], bid, it["quote"])
        if p["entities"]:
            bid = f"{pid}-ent"; add(bid, "branch", "Key concepts", top)
            for n, e in enumerate(p["entities"][:8]): add(f"{bid}-{n}", "entity", e, bid)
    if brief["shared_concepts"]:
        add("shared", "branch", "Shared concepts", "root")
        for n, e in enumerate(brief["shared_concepts"][:8]): add(f"shared-{n}", "entity", e, "shared")
    return {"nodes": nodes, "edges": edges, "mode": "mindmap", "related": {"shared_entity": [], "semantic_similarity": [], "citations": []}}
