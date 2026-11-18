#!/usr/bin/env python
"""Ingest a bounded subset of peS2o. Example: python scripts/ingest_pes2o.py --profile small"""
import argparse, json, logging, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import load_config
from ingestion.pes2o_loader import ingest

ap = argparse.ArgumentParser()
ap.add_argument("--profile", choices=["dev", "small", "medium"], default="dev")
ap.add_argument("--limit", type=int, help="override profile document limit")
ap.add_argument("--shard", type=int, default=0)
ap.add_argument("--split", default="train")
ap.add_argument("--quota-per-domain", type=int, help="cap docs per weak domain label for stratified sampling")
ap.add_argument("--no-resume", action="store_true")
ap.add_argument("--strategy", default="section", choices=["fixed", "sentence", "section"])
ap.add_argument("--db")
ap.add_argument("--local-file", help="read a local .json(.gz) shard instead of streaming")
a = ap.parse_args()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
limit = a.limit or load_config("retrieval")["ingest"]["profiles"][a.profile]
rep = ingest(limit, split=a.split, shard=a.shard, quota_per_domain=a.quota_per_domain, resume=not a.no_resume,
             chunk_strategy=a.strategy, db_path=a.db, local_file=a.local_file)
print(json.dumps(rep["stats"], indent=2))
