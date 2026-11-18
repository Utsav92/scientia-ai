#!/usr/bin/env python
"""Build BM25 + FAISS index over chunks. Reports measured throughput, size and memory."""
import argparse, json, resource, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import OUT_DIR
from retrieval.hybrid import build_index

ap = argparse.ArgumentParser()
ap.add_argument("--owner", default="")
ap.add_argument("--model", default="minilm")
ap.add_argument("--name", default="")
ap.add_argument("--limit", type=int)
a = ap.parse_args()
r = build_index(a.owner, a.name, a.model, chunk_limit=a.limit, progress=lambda f, m: print(f"\r{m}", end="", flush=True))
r["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, 1)  # macOS reports bytes
print("\n" + json.dumps(r, indent=2))
(OUT_DIR / "evaluations").mkdir(parents=True, exist_ok=True)
(OUT_DIR / "evaluations" / f"index_build_{a.model}_{a.name or 'default'}.json").write_text(json.dumps(r, indent=2))
