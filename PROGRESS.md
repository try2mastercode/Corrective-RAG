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
- [x] **Phase 1** — Basic Local RAG — DONE (commits `044a77f`, `d632782`)
- [x] **Phase 2** — Retrieval Grading — DONE, awaiting commit approval
- [ ] **Phase 3** — Corrective Query Rewriting and Re-Retrieval — NEXT
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
| 1 (fixup) | `d632782` | chore: record phase 1 commit hash in progress tracker |
| 2 | _pending_ | feat: add retrieval grading |

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

## Completed phase detail — Phase 2 (Retrieval Grading)

All checklist items done. Verified via `pytest` (30 passed — 14 new grader unit tests) and a
live HTTP smoke test against real Ollama/`llama3.2:3b`: indexed two single-topic documents
(a radio telescope fact, an unrelated zoning fact), asked a question about the telescope, and
confirmed via `/ask` with `debug: true` that the relevant chunk graded `RELEVANT`/0.9 and the
unrelated chunk graded `IRRELEVANT`/0.0, giving an overall `MEDIUM` quality decision — matching
expectations exactly.

**Debugging note worth remembering:** an early smoke-test attempt put two unrelated topics in
one small text file, which chunking merged into a *single* chunk (short enough to fit under the
600-token limit). Grading that mixed-topic chunk produced an internally inconsistent result
(label `RELEVANT` but score `0.0`) — not a code bug, but the small 3B model getting confused by
mixed-topic content in one passage. Re-tested with properly separated single-topic documents and
grading was consistent. Worth remembering for Phase 7's evaluation dataset design: keep
distractor/multi-topic test cases deliberate rather than accidental.

Key artifacts added:
- `app/retrieval/grader.py` — `grade_chunk`/`grade_chunks` (LLM-based, JSON-only prompt,
  evidence explicitly marked untrusted/non-instructional per the same prompt-injection pattern
  as Phase 1's answer prompt), retry-on-malformed-JSON (`grader_max_retries`, default 2, falls
  back to a safe `IRRELEVANT`/0.0 grade after exhausting retries), score clamped to [0,1], label
  validated against `{RELEVANT, PARTIALLY_RELEVANT, IRRELEVANT}`; `calculate_retrieval_quality`
  implementing the weighted formula from todo.md section 10 (`0.5*mean + 0.3*best +
  0.2*relevant_ratio` by default, all weights and the HIGH/MEDIUM/LOW thresholds configurable
  via settings/`.env`)
- `app/core/config.py` / `.env.example` — new settings: `quality_weight_mean`,
  `quality_weight_best`, `quality_weight_relevant_ratio`, `retrieval_quality_high_threshold`,
  `retrieval_quality_medium_threshold`, `grader_max_retries`
- `app/core/models.py` — `RetrievalGrade`, `GradedChunk`, `RetrievalQualityResult`; `AskResponse`
  gained an optional `debug` field
- `app/api/routes_ask.py` — `/ask` now always grades retrieved chunks and sets
  `retrieval_status` to the HIGH/MEDIUM/LOW quality decision (was a flat "OK"/"NO_RESULTS" in
  Phase 1); full per-chunk grades + quality breakdown are included in the response only when
  `debug: true` is passed, so normal calls pay the grading LLM-call cost but not the payload size
- `tests/unit/test_grader.py` — JSON extraction/parsing edge cases, retry behavior via a fake
  `LLMClient`, quality-calculation thresholds

Known limitations / deliberate scope boundaries (per the phase-sequencing rule — do not act on
these until their designated phase):
- Grading is **diagnostic only** — it does not yet filter which chunks reach the answer
  generator, and a `LOW` quality decision does not yet trigger anything. Filtering/rewriting on
  a weak decision is explicitly Phase 3's job ("query rewriter... choose best evidence").
- Every `/ask` call now makes `1 (answer) + N (grading, one per retrieved chunk)` LLM calls —
  up to 9 total at the default `TOP_K=8`. This is a known latency cost; todo.md section 34
  explicitly defers "unnecessary grading calls" optimization to Phase 9, so no caching/dedup was
  added here.
- No query rewriting, correction loop, web fallback, evidence builder, or claim verification yet
  (Phases 3–6, unchanged from Phase 1's limitations list above).

## Current phase detail — Phase 3 (Corrective Query Rewriting and Re-Retrieval) — not started

Scope (from todo.md section 38 / section 11-12):
- [ ] Query rewriter (`app/correction/query_rewriter.py`) — LLM call producing a structured
  `{original_query, rewritten_query, reason}`, must not answer the question, must preserve intent
- [ ] Corrective retrieval controller (`app/correction/controller.py`) — orchestrates:
  retrieve → grade → if quality is LOW/MEDIUM (below configurable bar) → rewrite → retrieve again
  → grade again → merge/pick best evidence
- [ ] Bounded rounds via existing `MAX_RETRIEVAL_ROUNDS` setting (already in config, unused so far)
- [ ] Repeated/equivalent-query detection to avoid pointless loops
- [ ] Result merging across rounds + re-ranking
- [ ] Before/after retrieval diagnostics (extend the existing `/ask` debug payload)
- [ ] Wire the controller into `/ask`, replacing the current single-shot retrieve-then-grade flow
- [ ] Tests: successful correction (weak → strong after rewrite), failed correction (still weak
  after max rounds), no-correction-when-strong (avoid unnecessary rewrite)

Acceptance criteria: a deliberately weak initial retrieval must trigger query rewriting and a
second retrieval, while a strong initial retrieval must avoid unnecessary correction.

### Next action when resuming
1. Re-read this file top to bottom, then skim `todo.md` sections 11-12 for the rewrite/correction
   spec, and section 27 (`app/correction/` module layout).
2. Ask the user for permission before starting implementation, per the standing workflow rule
   (permission checkpoints are back in effect as of Phase 2 — see the note above).
3. Implement the checklist above, run tests, review `git diff`, ask for permission before
   committing, commit as `feat: add corrective query rewriting`, update this file's Phase status
   table and commit log, then move to Phase 4 (and ask about the web search provider decision
   that was deferred back in Phase 0).
