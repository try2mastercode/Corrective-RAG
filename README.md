# Corrective RAG — Self-Evaluating Local Llama

A local-first Retrieval-Augmented Generation (RAG) system that doesn't blindly trust its own
retrieval. It grades retrieved chunks for relevance, rewrites weak queries and re-retrieves,
optionally falls back to web search, builds a normalized evidence layer, generates an answer
grounded in that evidence, and checks the answer's claims for support before returning it.
Retrieval and answer quality are measured with RAGAS, comparing a baseline RAG pipeline against
the full corrective pipeline (CRAG).

See [todo.md](todo.md) for the original specification and [PROGRESS.md](PROGRESS.md) for the
full phase-by-phase build history, decisions, and debugging notes.

## Status

**All 10 phases (0–9) complete.** Full pipeline: ingestion → chunking → embeddings → retrieval →
grading → corrective query rewriting → web fallback → evidence building → grounded generation →
claim verification/correction → RAGAS evaluation → vanilla JS frontend → observability/hardening.

## Stack

- **Backend:** Python 3.11 + FastAPI
- **LLM:** local, via [Ollama](https://ollama.com) — `llama3.2:3b` (pipeline), `qwen2.5:7b-instruct`
  (RAGAS judge — see [Evaluation](#evaluation))
- **Embeddings:** local, in-process via `sentence-transformers` — `BAAI/bge-small-en-v1.5`
- **Vector store:** Chroma
- **Web search:** DuckDuckGo (via `ddgs`), no API key
- **Frontend:** HTML + CSS + vanilla JavaScript (no framework, no build step)
- **Evaluation:** RAGAS `0.1.21` (pinned — see [Limitations](#limitations))

No Docker or containers are used anywhere in this project.

## Installation

### Prerequisites

- Python 3.11 (a different version may not have compatible wheels for `torch` /
  `sentence-transformers` / `chromadb` / `ragas`)
- [Ollama](https://ollama.com) installed and running locally

### 1. Pull the local models

```bash
ollama pull llama3.2:3b
ollama pull qwen2.5:7b-instruct
```

The second model is only used as RAGAS's judge during evaluation — skip it if you don't plan to
run `scripts/evaluate.py` (the app itself still needs `llama3.2:3b`, or whatever `LLM_MODEL` you
configure).

### 2. Create a virtual environment and install dependencies

```bash
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

### 3. Configure environment variables

```bash
copy .env.example .env
```

Adjust values in `.env` as needed (model names, thresholds, `WEB_SEARCH_ENABLED`, etc.).

## Running

```bash
# 1. Start the local LLM server (if not already running as a service)
ollama serve

# 2. Start the backend
uvicorn app.main:app --reload

# 3. Serve the frontend (any static file server works)
python -m http.server 5500 --directory frontend
```

Open `http://localhost:5500`, set the API base URL to your backend's address (default
`http://127.0.0.1:8000`), and use the Ask / Documents / Evaluation tabs.

Check the backend directly:

```bash
curl http://127.0.0.1:8000/health
```

### CLI usage

```bash
python -m scripts.ingest ./data/raw/some_document.pdf
python -m scripts.ask "What does the document say about X?"
python -m scripts.evaluate --limit 5              # small interactive evaluation run
python -m scripts.benchmark --limit 10            # fast CRAG-only latency/rate check, no RAGAS
```

## Architecture

```text
                         +----------------+
                         |     User       |
                         +-------+--------+
                                 |
                                 v
                    +------------------------+
                    | Vanilla JS Frontend /   |
                    | FastAPI /ask endpoint   |
                    +------------+-----------+
                                 |
                                 v
                    +------------------------+
                    | Corrective Controller   |
                    | (app/correction/)       |
                    +------------+-----------+
                                 |
              +------------------+------------------+
              |                                      |
              v                                      |
      +---------------+                              |
      | Chroma Vector |                               |
      | Store         |                               |
      +------+--------+                               |
             |                                         |
             v                                         |
      +---------------+                                |
      | Retriever     |                                |
      +------+--------+                                |
             |                                          |
             v                                          |
      +---------------+     weak      +---------------+ |
      | Chunk Grader  |-------------->| Query Rewriter| |
      +------+--------+               +-------+-------+ |
             | strong                         |          |
             |                                v          |
             |                       retrieve again ------
             |                                |
             +-----------------<--------------+
                                 |
                        still weak & enabled?
                                 |
                                 v
                       +------------------+
                       | Web Search        |
                       | (DuckDuckGo)      |
                       +--------+---------+
                                 |
                                 v
                       +------------------+
                       | Evidence Builder  |
                       | (dedup, E1/E2 IDs,|
                       |  context cap)     |
                       +--------+---------+
                                 |
                                 v
                       +------------------+
                       | Local Llama       |
                       | (answer generator)|
                       +--------+---------+
                                 |
                                 v
                       +------------------+
                       | Claim Extraction /|
                       | Verification /    |
                       | Correction Loop   |
                       +--------+---------+
                                 |
                                 v
                              Answer
                     (with sources, retrieval_status,
                      grounding_status, run_id)
```

Module layout (`app/`): `ingestion/` (loaders, chunking, indexing) · `embeddings/` (local
sentence-transformers) · `retrieval/` (vector store, retriever, grader) · `correction/` (query
rewriter, corrective + web-fallback controller) · `web/` (DuckDuckGo search) · `generation/`
(evidence builder, prompts, answer generation) · `verification/` (claim extraction, verification,
correction) · `evaluation/` (dataset, RAGAS runner, reports) · `core/` (config, models,
dependency wiring, request tracing) · `api/` (FastAPI routes) · `llm/` (Ollama client, shared
JSON-parsing helper).

## Example walkthrough

```text
Q: "Who designed the Halvorsen Array?"

1. Retrieve top-k chunks from Chroma.
2. Grade each chunk RELEVANT / PARTIALLY_RELEVANT / IRRELEVANT; compute an overall quality score.
3. If quality isn't HIGH: rewrite the query, retrieve again (bounded by MAX_RETRIEVAL_ROUNDS).
4. If still weak and web fallback is enabled + requested: search DuckDuckGo, grade those results too.
5. Build a deduplicated, size-capped evidence list with stable IDs (E1, E2, ...).
6. Generate an answer citing those IDs, evidence explicitly marked untrusted/non-instructional
   in the prompt (protects against prompt injection in retrieved or web content).
7. Extract the answer's factual claims and verify each against the evidence.
8. If any claim is unsupported: regenerate a corrected answer (bounded by
   MAX_ANSWER_CORRECTIONS), or prefix the answer with an explicit uncertainty notice if
   correction doesn't resolve it.
9. Return the answer with sources, retrieval_status, grounding_status, and a run_id.
```

Try it with `debug: true` on `POST /ask` (or the frontend's Debug mode checkbox) to see every
intermediate step: retrieval rounds, rewrites, web results, the built evidence, and per-claim
verification results.

## Evaluation

```bash
python -m scripts.evaluate --limit 5              # quick check
python -m scripts.evaluate                        # full 24-question dataset (see below for time)
python -m scripts.evaluate --web-fallback --output data/evaluation/report_web.md
```

This indexes `data/evaluation/corpus/` (8 short fictional documents, deliberately cross-
referenced and overlapping for multi-hop/distractor questions), runs every question in
`data/evaluation/dataset.json` through both the baseline pipeline (retrieve → generate, no
grading/correction/verification) and the full CRAG pipeline, computes RAGAS metrics
(faithfulness, answer relevancy, context precision, context recall) on both, and writes a
Markdown + JSON report.

**RAGAS uses a separate, larger local judge model** (`RAGAS_JUDGE_MODEL`, default
`qwen2.5:7b-instruct`) rather than the pipeline's own `llama3.2:3b`. RAGAS does its own internal
multi-step LLM prompting to compute metrics, and testing showed the smaller model produces
unreliable scores (a `faithfulness: 0.0` for an obviously faithful answer) while the larger model
is accurate but much slower on CPU (~55-60s per metric per question). **A full run of the
24-question dataset with all 4 metrics across both pipelines takes on the order of 3 hours on
CPU-only hardware** — use `--limit` for interactive checks, or `scripts/benchmark.py` for a fast
RAGAS-free latency/behavior check. A real (small) run's output is checked in at
[`data/evaluation/report.md`](data/evaluation/report.md).

## Limitations

Accumulated across the build (see [PROGRESS.md](PROGRESS.md) for the full reasoning behind each):

- **Evaluation dataset is 24 questions**, not the 50+ todo.md asks for. Extending it is
  mechanical (more JSON entries in `data/evaluation/dataset.json` against a larger corpus), but
  every question added multiplies the multi-hour RAGAS runtime described above.
- **RAGAS is pinned to `0.1.21`** with `langchain==0.2.17` / `langchain-community==0.2.19`. The
  newest RAGAS (0.4.x) hard-imports a `langchain_community` submodule that no longer exists in
  current `langchain-community` releases and fails at import time. If upgrading RAGAS, expect to
  re-verify this whole chain.
- **Evidence ranking doesn't unify across sources.** Local chunks are ranked by grader score;
  web-fallback results are appended after, ranked only among themselves. There's no principled
  way implemented to compare vector-similarity scores against web-search rank against grader
  confidence on one scale.
- **No formal `ANSWERABLE` / `ANSWERABLE_WITH_CAVEAT` / `INSUFFICIENT_EVIDENCE` decision enum.**
  `retrieval_status` (HIGH/MEDIUM/LOW/WEB_FALLBACK/NO_RESULTS) and `grounding_status`
  (SUPPORTED/UNSUPPORTED) together cover the same practical ground today.
- **URL-based document ingestion isn't implemented** — only file uploads (PDF/TXT/MD/DOCX).
  todo.md lists URL ingestion as "where useful"; only web *search* fallback was built.
  Correspondingly, URL-content sanitization for that ingestion path doesn't apply here.
- **No rate limiting or hardened request-size streaming limits** — this is an explicitly
  localhost-only, single-user local tool (todo.md's rate-limiting requirement is itself
  conditional on "if exposed outside localhost"). Upload size is capped (20MB) at the application
  level after the body is read, not via streaming enforcement.
- **The in-memory run trace store** (`GET /runs/{run_id}`, `GET /metrics`) is not persisted —
  it resets on backend restart and keeps only the most recent 500 runs.
- **Retrieval quality scoring can look worse than the actual answer is** on small/diverse
  corpora: with the default `TOP_K=8` against an 8-document evaluation corpus, every query
  retrieves essentially the whole corpus, so `retrieval_status` often reads LOW even when the one
  genuinely relevant chunk was found and correctly used (see the real evaluation report). Tune
  `TOP_K` down for small corpora.
- **The upload flow's OS file-picker interaction was verified by code review and equivalent curl
  calls**, not literal browser automation of the picker (a tooling limitation during development,
  not a known frontend defect).
