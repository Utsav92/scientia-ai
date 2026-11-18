#!/usr/bin/env python
"""Run extraction over stored docs and write measured quality stats to outputs/evaluations/."""
import argparse, json, sys, time, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import connect, OUT_DIR
from extraction.findings import extract_paper
from rag.synthesis import get_llm

ap = argparse.ArgumentParser()
ap.add_argument("--method", choices=["rules", "llm"], default="rules")
ap.add_argument("--limit", type=int, default=0, help="0 = all")
ap.add_argument("--seed", type=int, default=7)
a = ap.parse_args()
con = connect()
ids = [r[0] for r in con.execute("SELECT id FROM documents WHERE owner=''")]
random.Random(a.seed).shuffle(ids)
ids = ids[:a.limit] if a.limit else ids
llm = get_llm("openai_compatible") if a.method == "llm" else None
agg = {"docs": 0, "parse_ok": 0, "fell_back": 0, "dropped_ungrounded": 0, "items_kept": 0, "schema_errors": 0, "entities": 0, "with_findings": 0, "with_methodology": 0, "with_rq": 0, "errors": 0}
t0 = time.time()
for i, d in enumerate(ids, 1):
    try:
        r = extract_paper(d, "", llm)
    except Exception as e:
        agg["errors"] += 1; continue
    ex, st = r["extraction"], r["stats"]
    agg["docs"] += 1
    agg["parse_ok"] += bool(st.get("parse_ok", True)); agg["fell_back"] += bool(st.get("fell_back_to_rules")); agg["schema_errors"] += "schema_error" in st
    agg["dropped_ungrounded"] += ex["dropped_ungrounded"]
    agg["items_kept"] += sum(len(ex[k]) for k in ("datasets", "findings", "quantitative_results", "limitations", "future_work")) + sum(bool(ex[k]) for k in ("research_question", "hypothesis", "methodology"))
    agg["entities"] += len(ex["entities"]); agg["with_findings"] += bool(ex["findings"]); agg["with_methodology"] += bool(ex["methodology"]); agg["with_rq"] += bool(ex["research_question"])
    if i % 25 == 0: print(f"{i}/{len(ids)} {time.time()-t0:.0f}s", flush=True)
agg["seconds"] = round(time.time() - t0, 1)
agg["ungrounded_rate"] = round(agg["dropped_ungrounded"] / max(agg["dropped_ungrounded"] + agg["items_kept"], 1), 3)
agg["method"] = a.method; agg["llm"] = llm.name if llm else None
(OUT_DIR / "evaluations").mkdir(parents=True, exist_ok=True)
(OUT_DIR / "evaluations" / f"extraction_{a.method}.json").write_text(json.dumps(agg, indent=2))
print(json.dumps(agg, indent=2))
