#!/usr/bin/env python
"""Tiny (200 doc) ingest for smoke tests."""
import subprocess, sys
sys.exit(subprocess.call([sys.executable, "scripts/ingest_pes2o.py", "--limit", "200", "--quota-per-domain", "50", "--no-resume"]))
