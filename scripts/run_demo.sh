#!/usr/bin/env bash
# Ingest 1k docs (if DB empty), build the index, then start API (:8000) and UI (:5173).
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
[ -f datasets/processed/scientia.db ] || $PY scripts/ingest_pes2o.py --profile dev --quota-per-domain 300
[ -f outputs/indexes/shared/default/faiss.index ] || $PY scripts/build_index.py
export SCIENTIA_ADMIN_EMAILS=${SCIENTIA_ADMIN_EMAILS:-admin@example.org}
$PY -m uvicorn backend.main:app --port 8000 &
(cd frontend && npm run dev)
