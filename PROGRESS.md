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
2. After every phase: implement → test → review diff → commit → move to next phase.
3. Never add Claude/AI as co-author/contributor anywhere (commits, README, metadata).
4. No Docker/containers/Kubernetes, ever.
5. Frontend is HTML+CSS+vanilla JS only, no frameworks.
6. Local Llama model is the primary LLM, no paid hosted LLM for the core pipeline.
7. Don't claim a feature is done without implementing AND validating it.

**Note on permission checkpoints:** originally every phase paused for explicit user go-ahead
before committing. On 2026-08-30 the user said not to ask every time and to just proceed through
Phase 1, then stop. Phase 1 was therefore implemented and committed without an interim approval
ask. **When resuming for Phase 2, go back to asking for permission before each phase's commit**
unless the user says otherwise again.

## Phase status

- [x] **Phase 0** — Repository and Local Environment — DONE (commit `cee5874`)
- [x] **Phase 1** — Basic Local RAG — DONE (commit pending, see below)
- [ ] **Phase 2** — Retrieval Grading — NEXT (stopped here for the day, per user request)
- [ ] Phase 3 — Corrective Query Rewriting and Re-Retrieval
- [ ] Phase 4 — Web Search Fallback (need provider decision — see above)
- [ ] Phase 5 — Evidence Builder and Grounded Generation
- [ ] Phase 6 — Hallucination / Claim Verification
- [ ] Phase 7 — RAGAS Evaluation and Benchmarking
- [ ] Phase 8 — Vanilla HTML/CSS/JS Frontend
- [ ] Phase 9 — Observability, Security, Testing, Hardening

## Commit log

| Phase | Commit hash | Message |
|---|---|---|
| 0 | `cee5874` | chore: initialize local rag project |
| 1 | `044a77f` | feat: implement basic local rag |

## Completed phase detail — Phase 0

All checklist items done, committed as `cee5874`. Key artifacts: `.venv/` (Python 3.11.9, not
committed), `app/core/config.py`, `app/api/routes_health.py`, `app/main.py`,
`tests/unit/test_health.py`, `README.md`, `.env.example`, `.gitignore`.

## Completed phase detail — Phase 1 (Basic Local RAG)

All checklist items done and verified both via `pytest` (16 passed, including a real
end-to-end integration test hitting the actual `llama3.2:3b` model through Ollama) and via a
manual HTTP smoke test (upload → index → retrieve → ask → list → delete, all via curl against
a running `uvicorn` server) — see session transcript for the exact request/response pairs.

Key artifacts added:
- `app/ingestion/loaders.py` — PDF/TXT/MD/DOCX loaders, content-hash `document_id`
- `app/ingestion/chunking.py` — recursive splitter, ~600 token chunks / 100 token overlap
  (configurable), normalization, deterministic `chunk_id`, duplicate-chunk skip
- `app/embeddings/local.py` — `sentence-transformers` wrapper (`BAAI/bge-small-en-v1.5`)
- `app/retrieval/vector_store.py` — Chroma wrapper: add/delete/search/search_with_scores/
  list_documents/rebuild_index, plus an embedding-model-mismatch guard
- `app/retrieval/retriever.py` — top-k retrieval returning `RetrievedChunk` with scores
- `app/llm/ollama.py` — Ollama `/api/chat` client (non-streaming, temperature control)
- `app/generation/prompts.py` / `app/generation/answer.py` — grounded answer prompt that
  explicitly labels evidence as untrusted data (early prompt-injection hardening, ahead of
  Phase 9's full treatment) and cites `[1]`/`[2]`-style markers
- `app/core/models.py` — shared Pydantic models; `app/core/dependencies.py` — factory functions
  wiring settings → embeddings/vector store/retriever/LLM, shared by API routes and CLI scripts
- `app/api/routes_documents.py` (`/documents/upload`, `/documents/index`, `GET /documents`,
  `DELETE /documents/{id}` — filename sanitized, path-traversal guarded, 20MB upload cap) and
  `app/api/routes_ask.py` (`/retrieve`, `/ask`)
- `scripts/ingest.py`, `scripts/ask.py` — CLI entry points
- Tests: `tests/unit/test_loaders.py`, `test_chunking.py`, `test_vector_store.py`,
  `tests/integration/test_ask_pipeline.py` (skips gracefully if Ollama isn't running)

Known limitations to revisit in later phases (by design — out of Phase 1 scope):
- No retrieval grading yet (Phase 2) — retrieval quality isn't evaluated, just returned as-is
- No query rewriting/correction loop yet (Phase 3)
- No web fallback yet (Phase 4)
- No formal Evidence Builder with stable cross-stage evidence IDs yet (Phase 5) — citations in
  `/ask` responses are just the retrieval order, not a deduplicated/ranked evidence layer
- No claim verification / hallucination check yet (Phase 6)
- `rebuild_index()` on `ChromaVectorStore` is implemented but not yet exercised by any
  re-indexing workflow (relevant when the embedding model changes)

## Current phase detail — Phase 2 (Retrieval Grading) — not started

Scope (from todo.md section 38 / section 9-10):
- [ ] Retrieval grader (`app/retrieval/grader.py`) — LLM call that scores each retrieved chunk
- [ ] Structured JSON output (score, label RELEVANT/PARTIALLY_RELEVANT/IRRELEVANT, reason)
- [ ] Retry handling for malformed JSON output
- [ ] Overall retrieval-quality score (weighted formula per todo.md section 10, configurable)
- [ ] Configurable thresholds (`RELEVANCE_THRESHOLD` already in `.env.example`/`config.py`)
- [ ] Grading logs
- [ ] Unit tests for grading (parsing, malformed output, thresholds)
- [ ] Debug retrieval view (expose grading in `/ask` when `debug: true`)

Acceptance criteria: for every retrieval, the system can explain internally which chunks are
useful and whether retrieval is strong enough to continue.

### Next action when resuming
1. Re-read this file top to bottom, then skim `todo.md` section 9-10 for the grading prompt spec.
2. **Ask the user for permission before starting implementation** (the "just proceed" instruction
   from 2026-08-30 was scoped to reaching the end of Phase 1 only — see the workflow-rules note
   above).
3. Implement the checklist above, run tests, review `git diff`, ask for permission again before
   committing, commit as `feat: add retrieval grading`, update this file's Phase status table
   and commit log, then move to Phase 3.
