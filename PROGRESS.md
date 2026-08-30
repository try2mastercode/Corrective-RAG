# CRAG Project — Progress Tracker

> Read this file first if resuming after a context reset. It records what's done,
> what's decided, and what's next. The full spec lives in [todo.md](todo.md).

## Locked-in decisions (Phase 0)

| Decision | Choice | Notes |
|---|---|---|
| LLM | `llama3.2:3b` via Ollama | Pulled instead of qwen2.5:7b-instruct to satisfy the spec's Llama requirement. Ollama models stored at `D:\ollama-models`. |
| Python | 3.11.9 (via `py -3.11`) | Chosen over default 3.14.3 for ML dependency (torch/chromadb/sentence-transformers/ragas) compatibility. |
| Embeddings | `sentence-transformers`, in-process | Model: `BAAI/bge-small-en-v1.5`. No extra server. |
| Vector store | Chroma | Per spec default. |
| Web search (Phase 4) | **Not yet decided** — deferred until Phase 4 | Options on the table: DuckDuckGo (no key) or Tavily/SerpAPI/Brave (user has key, TBD which). Ask again when Phase 4 starts. |
| Backend | FastAPI | Per spec. |
| Frontend | HTML/CSS/vanilla JS only | Per spec, no frameworks. |
| Git identity | Uses existing global git config (Tharun Sridhar) | No AI attribution ever — see todo.md rules. |

## Workflow rules (from todo.md, do not violate)

1. Execute phases strictly in order (0 → 9). Never skip or silently combine.
2. After every phase: implement → test → review diff → **ask user for permission** → commit → move to next phase.
3. Never add Claude/AI as co-author/contributor anywhere (commits, README, metadata).
4. No Docker/containers/Kubernetes, ever.
5. Frontend is HTML+CSS+vanilla JS only, no frameworks.
6. Local Llama model is the primary LLM, no paid hosted LLM for the core pipeline.
7. Don't claim a feature is done without implementing AND validating it.

## Phase status

- [x] **Phase 0** — Repository and Local Environment — DONE, awaiting commit approval
- [ ] Phase 1 — Basic Local RAG
- [ ] Phase 2 — Retrieval Grading
- [ ] Phase 3 — Corrective Query Rewriting and Re-Retrieval
- [ ] Phase 4 — Web Search Fallback (need provider decision — see above)
- [ ] Phase 5 — Evidence Builder and Grounded Generation
- [ ] Phase 6 — Hallucination / Claim Verification
- [ ] Phase 7 — RAGAS Evaluation and Benchmarking
- [ ] Phase 8 — Vanilla HTML/CSS/JS Frontend
- [ ] Phase 9 — Observability, Security, Testing, Hardening

## Commit log

_(filled in as each phase completes)_

| Phase | Commit hash | Message |
|---|---|---|
| — | — | — |

## Current phase detail — Phase 0

Scope (from todo.md section 38):
- [x] Confirm Ollama runtime available (`ollama version 0.33.2` found)
- [x] Pull `llama3.2:3b` (2.0 GB, confirmed via `ollama list`)
- [x] Initialize Git repository (`git init`)
- [x] Create Python project structure (per todo.md section 28)
- [x] Create virtual environment (Python 3.11.9, `.venv/`)
- [x] Configure `.gitignore`
- [x] Create `.env.example`
- [x] Confirm local embedding model loads (BAAI/bge-small-en-v1.5 via sentence-transformers, verified 384-dim output)
- [x] Confirm Python dependencies install correctly (`pip install -e ".[dev]"` succeeds)
- [x] Add basic application configuration (`app/core/config.py`)
- [x] Add `/health` endpoint (`app/api/routes_health.py`, checks Ollama reachability too)
- [x] Add initial README
- [x] Verify the application starts locally (`uvicorn app.main:app`, `/health` returned 200 with `llm_status: reachable`)
- [x] Smoke test added (`tests/unit/test_health.py`), `pytest` passes (1 passed)
- [ ] Git commit: `chore: initialize local rag project` — **awaiting user go-ahead**

### Next action when resuming
If the commit above doesn't exist yet, ask the user for permission, then commit with the
message above and flip Phase 0 to fully DONE. Once committed: ask user for permission to
start Phase 1, update the Phase status table, and repeat the implement→test→review→approve→
commit pattern for each subsequent phase.
