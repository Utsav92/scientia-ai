#!/usr/bin/env python
"""Build the shared knowledge graph from stored extractions (run scripts/run_extraction.py first)."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from knowledge_graph.graph_builder import build_graph, save_graph
from retrieval.hybrid import Retriever, index_dir

t = time.time()
ret = Retriever() if (index_dir("") / "faiss.index").exists() else None
g = build_graph("", method="rules", retriever=ret)
save_graph(g)
print(json.dumps({**g.graph["stats"], "seconds": round(time.time() - t, 1), "semantic_edges_included": ret is not None}, indent=2))
