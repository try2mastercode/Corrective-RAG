# Corrective RAG — Self-Evaluating Local Llama

A local-first Retrieval-Augmented Generation (RAG) system that doesn't blindly trust its own
retrieval. It grades retrieved chunks for relevance, rewrites weak queries and re-retrieves,
optionally falls back to web search, generates an answer grounded in the retrieved evidence, and
checks that answer for unsupported claims before returning it. Retrieval and answer quality are
measured with RAGAS, comparing a baseline RAG pipeline against the full corrective pipeline (CRAG).

This project is being built in sequential phases — see [todo.md](todo.md) for the full
specification and [PROGRESS.md](PROGRESS.md) for current status and decisions made along the way.

## Status

**Phase 1 (basic local RAG) complete.** Documents can be uploaded, indexed, retrieved, and
answered by the local Llama model with source citations. Retrieval grading, corrective
query rewriting, web fallback, a formal evidence builder, hallucination verification, RAGAS
evaluation, and the frontend are not yet implemented — see [PROGRESS.md](PROGRESS.md) for the
phase-by-phase plan and status.

Try it yourself:

```bash
uvicorn app.main:app --reload
python -m scripts.ingest ./data/raw/some_document.pdf
python -m scripts.ask "What does the document say about X?"
```

## Stack

- **Backend:** Python 3.11 + FastAPI
- **LLM:** local, via [Ollama](https://ollama.com) — `llama3.2:3b`
- **Embeddings:** local, in-process via `sentence-transformers` — `BAAI/bge-small-en-v1.5`
- **Vector store:** Chroma
- **Frontend:** HTML + CSS + vanilla JavaScript (no framework)
- **Evaluation:** RAGAS

No Docker or containers are used anywhere in this project.

## Installation

### Prerequisites

- Python 3.11 (a different version may not have compatible wheels for `torch` /
  `sentence-transformers` / `chromadb` / `ragas`)
- [Ollama](https://ollama.com) installed and running locally

### 1. Pull the local model

```bash
ollama pull llama3.2:3b
```

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

Adjust values in `.env` as needed (model name, thresholds, etc.).

## Running

```bash
# 1. Start the local LLM server (if not already running as a service)
ollama serve

# 2. Start the backend
uvicorn app.main:app --reload
```

Check that everything is wired up:

```bash
curl http://127.0.0.1:8000/health
```

## Architecture

See [todo.md](todo.md) section 46 for the full architecture diagram. In short:

```text
Question -> Retrieve -> Grade -> Rewrite if weak -> Retrieve again
         -> Web fallback if still weak -> Evidence Builder
         -> Generate (local Llama) -> Verify claims -> Answer
```

## Evaluation

RAGAS-based evaluation (baseline RAG vs. CRAG) will be added in a later phase — see
[PROGRESS.md](PROGRESS.md) for the phase plan.

## Limitations

This section will be filled in as components are implemented and their failure modes are
understood (tracked in [PROGRESS.md](PROGRESS.md)).
