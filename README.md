# SCIENTIA AI — Scientific Knowledge Intelligence

Evidence-grounded research search over scientific papers: hybrid retrieval (BM25 + dense + RRF), cross-encoder
reranking, cited answers with a **citation-verification** stage, private PDF libraries, FastAPI backend, React UI.

## Status (honest)

| Area | State |
|---|---|
| peS2o streaming ingestion (resumable, dedup, validation, licence record, error report) | **Done**, run on 10,000 real docs |
| Rule-based cleaning / section detection / 3 chunkers (exact char offsets) | **Done**, tested |
| BM25 + FAISS dense + RRF hybrid + cross-encoder rerank | **Done**, measured on BEIR SciFact |
| RAG pipeline, abstention, claim-level NLI citation verification | **Done** (extractive by default; **tested with a live local LLM**: Qwen2.5-3B-Instruct-4bit via `mlx-lm` — see below) |
| PDF upload → private per-user index; auth (JWT); jobs; audit log | **Done**, tested incl. cross-user isolation |
| React UI: ask/search, citations + evidence, library upload, evaluation charts | **Built + type-checked; not yet visually reviewed in a browser** |
| Entity / finding / relation extraction (rules baseline + local-LLM with verbatim-quote grounding) | **Done**, run on all 10k (rules) and 100 (LLM); no gold labels, so **no accuracy/F1 claimed** |
| Knowledge graph (NetworkX; paper/entity/finding nodes; extracted vs semantic vs citation edges), queries, cluster detection, Cypher export | **Done**, built on the 10k corpus; Neo4j push **untested** (no server) |
| API `/api/research/extract`, `/api/graph/*`; UI graph explorer (Cytoscape) + extraction panel | **Done + tested via API**; UI type-checked/built but **never viewed in a browser** (headless Chrome could not reach local servers in this sandbox) |
| Cross-paper comparison (`POST /api/research/compare`, UI “Compare Studies”) | **Done**: side-by-side table of grounded quotes, exact entity overlap, optional NLI *candidate* contradictions (baseline signal, no gold labels, **not validated**). Tested via unit + API tests; UI type-checked/built, **not viewed in a browser**. Rules extraction is sparse on many papers (empty cells = not stated). |
| Studio (`/api/studio/*`, UI “Studio”): paper-scoped chat, overview, mind map, slides (+PDF), two-host audio overview, narrated video | **Done + tested** (unit + API tests incl. per-user file isolation; every output type generated on real corpus papers; MP4/M4A verified with ffmpeg). **Extractive by design**: content is the paper's own sentences (rule-based extraction) arranged as slides/Q&A, spoken with offline macOS `say` voices — *not* model-written explanations like NotebookLM, so it can read stiffly and thin sections are skipped. **Slides and video are rendered with Remotion** (`video/`: animated title/quote/cards/steps/stats/concept-map/split scenes, synced captions, 1280×720 H.264; slide PNGs/PDF are stills of the same scenes) — falls back to a plain Pillow/ffmpeg renderer if `video/node_modules` or Node is missing. **Needs macOS `say` + `ffmpeg`; Remotion needs Node + `cd video && npm install && npx remotion browser ensure`.** UI type-checked/built, **not viewed in a browser**. |
| Embedding fine-tune (`python -m training.finetune_embedding`) | **Done, SciFact only**: dense nDCG@10 on 300 test queries 0.648 → 0.677 (single seed, no CI; trained on ~660 train queries, early-stopped on 150 dev queries at epoch 1; dev gain was only +0.001, so the test gain is modest evidence). Not yet wired into the default index. Raw: `outputs/evaluations/embedding_finetune_scifact.json` |
| Training: domain classifier, reranker fine-tune | **Not implemented — no model has been trained** |
| Neo4j, GROBID, OCR, citation/groundedness benchmarks, PostgreSQL, Docker | **Not implemented** |

## Reproduce
```bash
(cd video && npm install && npx remotion browser ensure)                         # optional: animated slides/video
scripts/setup_macos.sh
.venv/bin/python scripts/ingest_pes2o.py --profile small --quota-per-domain 2200   # 10k docs, ~100 s
.venv/bin/python scripts/build_index.py                                           # embeds chunks on MPS
.venv/bin/python -m evaluation.retrieval_eval scifact                             # BEIR SciFact table below
.venv/bin/python -m pytest                                                        # tests
SCIENTIA_ADMIN_EMAILS=you@example.org .venv/bin/uvicorn backend.main:app --port 8000
cd frontend && npm run dev                                                        # http://localhost:5173
```

## Measured results (Mac mini-class, 24 GB, MPS) — raw files in `outputs/evaluations/`
BEIR **SciFact**, 5,183 docs, 300 test queries. all-MiniLM-L6-v2 + ms-marco-MiniLM-L-6-v2. RRF params tuned on 150 *dev*
queries drawn from the train qrels only.

| System | nDCG@10 | Recall@10 | Recall@100 | MRR@10 |
|---|---|---|---|---|
| BM25 | 0.645 | 0.767 | 0.866 | 0.612 |
| Dense | 0.648 | 0.790 | 0.928 | 0.606 |
| Hybrid (RRF) | 0.681 | 0.824 | 0.962 | 0.640 |
| Hybrid + rerank (top-50) | 0.688 | 0.811 | 0.962 | 0.656 |

Reranking adds only +0.007 nDCG@10 on SciFact and lowers Recall@10 slightly; it costs ≈123 ms/query. Hybrid is the clear win.
Single run, no confidence intervals. SciFact is claim verification, not open question answering.

Local corpus index (11,894 chunks): embedding 720 chunks/s on MPS, 32 MB index, ≈1.1 GB peak RSS, warm query ≈45 ms retrieval + ≈90 ms rerank.

## Extraction and graph — measured, with caveats
Rules baseline over 10,000 docs: 13.8 s, 19,152 entities; findings found for ~46% of docs (short abstracts; conservative cues).
Local LLM (Qwen2.5-3B-4bit) on a random 100-doc sample: JSON parsed 89/100 (11 fell back to rules), **29.6% of proposed items rejected
because their quote was not verbatim in the source**, 0 schema errors, ≈3.8 s/doc. Raw: `outputs/evaluations/extraction_*.json`.
* **Grounding proves provenance, not correctness.** A quote can be real yet mislabeled (seen: a research question filed as a limitation) and a model that copies an
  injected sentence from a paper would pass the check. Treat extracted fields as evidence-linked *candidates*.
* **Entity precision is unmeasured.** Eyeballed spot-checks: method/dataset hits look good; `CHEMICAL` was ~60% in a 25-item sample (assay/gene names like `IC50`, `PI3K-`
  slip through). `yield`/`sensitivity` as METRIC are ambiguous. No trained NER model exists yet.
* Graph (10k papers): ~25k nodes, ~37k edges. **0 citation edges** — peS2o records carry no bibliography. `SIMILAR_TO` edges are embedding similarity (dashed in UI,
  labelled "not citations"). `add_citations()` accepts only verified (citing, cited) pairs between papers already in the graph.
* `EVALUATED_ON` is sparse (≈190 relations): the sentence-cooccurrence rule is conservative.
* View the UI yourself: `uvicorn backend.main:app --port 8765` and `cd frontend && SCIENTIA_API=http://127.0.0.1:8765 npx vite --host 127.0.0.1`.

## Things you should know
* **peS2o v2 has no title/domain fields.** The title is the first line of `text`; domain labels are a **keyword heuristic (weak supervision)**
  in `ingestion/weak_labels.py`. Domain filters and any classifier trained on them reflect that heuristic, not ground truth.
* **The ingested 10k slice is title+abstract only (`s2ag`)**; 96% of chunks have section `unlabeled`. Authors/DOI are absent for these records and are never invented.
* The corpus is a static snapshot. Answers about "latest" work say so; nothing is claimed current.
* **Small corpus ⇒ frequent abstention.** e.g. "diffusion models vs autoregressive Transformers for scientific data" correctly yields
  "cannot compare" because no indexed passage covers both terms. That is the intended behaviour, not a bug.
* Verification uses sentence-window NLI (a small NLI model scored whole abstracts as *neutral* even when they contained the claim verbatim).
  NLI is a signal, not proof; the abstention threshold (`ABSTAIN_RERANK_MIN = -3.0`) is **uncalibrated and weak** — measured with
  `python -m evaluation.abstention_eval` (SciFact, gold-removal protocol, raw: `outputs/evaluations/abstention_scifact.json`): the top rerank score separates
  answerable from unanswerable only modestly (test AUROC 0.70, 95% CI 0.67–0.72). At -3.0 the pipeline answers 94% of answerable but abstains on only 13% of
  unanswerable queries (a lower bound: qrels are incomplete). A dev-tuned threshold (2.28) gets 61% / 69% — better balanced, but it is SciFact-specific and
  was **not** adopted as the default. A logistic regression over 8 retrieval signals (`evaluation/abstention_model.py`) reached test AUROC 0.72 (CI 0.69–0.75), statistically indistinguishable from the single score, so it was **not** wired in either. Don't read the score as confidence; abstention currently relies mostly on the conjunctive-term check and NLI verification.
* **Local LLM (tested):** `.venv-llm/bin/python -m mlx_lm.server --model mlx-community/Qwen2.5-3B-Instruct-4bit --port 8081`, then set `llm.provider: openai_compatible`
  (already pointed at :8081 in `configs/models.yaml`). On 3 manual questions the verified answers were correct and cited, but a 3B model is terse, sometimes
  omits citations (those sentences are removed, so answers can be short), and varies its citation style (parser accepts `[1][2]`, `[1, 2]`, leading or trailing).
  A multi-source sentence counts as supported if *any* one cited passage entails it, which is looser than per-source checking. No systematic LLM evaluation has been run (n=3).
* Default generator is extractive (quotes retrieved sentences; no hallucination, limited fluency). Configure `configs/models.yaml` `llm.provider` for Ollama / OpenAI-compatible / HF.
* Retrieved text is treated as data: prompts fence passages and instruct the model to ignore instructions inside them (not yet red-teamed).
* Licences: peS2o is ODC-By (`datasets/manifests/pes2o_license.json`); underlying papers have their own licences — check before redistributing full text.
* Security defaults: shared-corpus ingest/index and training are admin-only (`SCIENTIA_ADMIN_EMAILS`); set `SCIENTIA_JWT_SECRET` in production.
