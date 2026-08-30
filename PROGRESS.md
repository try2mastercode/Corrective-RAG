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
- [x] **Phase 2** — Retrieval Grading — DONE (commit `f5e748a`)
- [x] **Phase 3** — Corrective Query Rewriting and Re-Retrieval — DONE, awaiting commit approval
- [ ] **Phase 4** — Web Search Fallback — NEXT (need provider decision — see above)
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
| 2 | `f5e748a` | feat: add retrieval grading |
| 3 | _pending_ | feat: add corrective query rewriting |

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

## Completed phase detail — Phase 3 (Corrective Query Rewriting and Re-Retrieval)

All checklist items done. Verified via `pytest` (42 passed — 12 new: 7 controller, 5 rewriter)
and two live HTTP smoke tests against real Ollama/`llama3.2:3b`:
1. Asked a question with **no relevant document in the corpus** (pizza dough ingredients,
   against a lighthouse-facts document): round 1 graded IRRELEVANT/LOW, the rewriter produced a
   sensible, intent-preserving expansion without inventing facts, round 2 (bounded by
   `MAX_RETRIEVAL_ROUNDS=2`) was still LOW, and the system correctly returned "I don't have
   enough retrieved evidence" rather than hallucinating from the unrelated document.
2. Asked a well-matched question against the same document: graded RELEVANT/HIGH on round 1,
   loop stopped immediately with **zero** rewrite calls — confirming strong retrieval avoids
   unnecessary correction.

**Design decision worth remembering:** each round's own STRONG/WEAK decision (which controls
whether the loop continues) is based on *that round's own retrieved set only* — matching the
spec's diagram, which grades immediately after each retrieve step. The *final* evidence set and
its reported quality (`final_quality`, surfaced as `retrieval_status`) are the union of
everything graded across all rounds, since that's what's actually handed to the answer
generator. These two numbers can legitimately diverge: a caught test case showed round 2 scoring
HIGH on its own retrieval while the merged final quality was only MEDIUM, because an earlier
weak chunk from round 1 was still dragging the merged average down. This is intentional
"merge, don't discard" behavior per todo.md section 12, not a bug — worth remembering before
"fixing" a future divergence like this.

Key artifacts added:
- `app/correction/query_rewriter.py` — `rewrite_query`: structured JSON output
  (`{rewritten_query, reason}`), same untrusted-content framing pattern as the grader/generator
  prompts, retry-on-malformed-JSON, falls back to the **unchanged original query** (not a guess)
  after exhausting retries
- `app/correction/controller.py` — `run_corrective_retrieval`: the retrieve→grade→rewrite→
  retrieve-again loop; grades are cached by `chunk_id` (always graded against the *original*
  question, never the rewritten one, since relevance to the user's actual question is what
  matters) so a chunk retrieved again in a later round isn't re-graded; repeated/equivalent-query
  detection (exact-match after normalization) stops the loop early if a rewrite doesn't actually
  change the query; final chunks are the merged, non-`IRRELEVANT` pool sorted by score
  ("keep the best chunks")
- `app/core/models.py` — `QueryRewrite`, `RetrievalRound`, `CorrectiveRetrievalResult`
- `app/api/routes_ask.py` — `/ask` now runs the full corrective loop instead of a single
  retrieve+grade pass; `debug: true` exposes all rounds, all rewrite attempts, and the final
  merged quality breakdown
- `tests/unit/test_query_rewriter.py`, `tests/unit/test_controller.py` (uses a `ScriptedLLM` test
  double that routes fake responses by system-prompt identity, and a `FakeRetriever` keyed by
  query string, to exercise multi-round scenarios without hitting a real model)

Known limitations / deliberate scope boundaries:
- No web search fallback yet — the pizza-dough smoke test above is exactly the scenario Phase 4
  will extend with a web search attempt after local correction is exhausted.
- Repeated-query detection is exact-string-match only (case/whitespace-normalized), not semantic
  similarity — todo.md section 12 just says "detect repeated/equivalent queries" without
  mandating a technique, and exact-match is the simplest thing that satisfies the stated need
  (stop obviously-pointless loops) without adding an embedding-similarity dependency here.
- No formal Evidence Builder with stable cross-stage evidence IDs yet (Phase 5) — citations in
  `/ask` responses are still just the final merged-and-sorted order.
- No claim verification / hallucination check yet (Phase 6).

## Current phase detail — Phase 4 (Web Search Fallback) — not started

Scope (from todo.md section 38 / section 13):
- [ ] **Ask the user which web search provider to use** — this was explicitly deferred from
  Phase 0 (see "Locked-in decisions" table above: options were DuckDuckGo/no-key, or
  Tavily/SerpAPI/Brave if the user has a key). Do this before writing the adapter.
- [ ] Web search adapter (`app/web/search.py`), provider configurable via `WEB_SEARCH_PROVIDER`
- [ ] Result normalization: URL, title, snippet/content, retrieval timestamp
- [ ] Source deduplication
- [ ] Provider timeout + failure handling (must not crash `/ask`; degrade gracefully)
- [ ] `WEB_SEARCH_ENABLED` feature flag (already in config/`.env.example`, unused so far)
- [ ] Trigger condition: local retrieval still weak after `run_corrective_retrieval` is exhausted
  AND `web_search_enabled` AND (`request.web_fallback` — already an `AskRequest` field, unused
  so far)
- [ ] Clear `LOCAL_DOCUMENT` vs `WEB_SOURCE` labeling — must never blur the two
- [ ] Tests: fallback triggers only when appropriate, timeout handling, provider failure handling

Acceptance criteria: the system uses web search only when configured and local retrieval remains
weak after corrective retrieval; web evidence is clearly distinguished from local documents.

### Next action when resuming
1. Re-read this file top to bottom, then skim `todo.md` section 13 for the web fallback spec.
2. **Ask the user for the web search provider decision first** (see checklist above) — this
   blocks implementation, unlike prior phases where the decision was already made.
3. Ask for permission before starting implementation (standing workflow rule).
4. Implement the checklist above, run tests, review `git diff`, ask for permission before
   committing, commit as `feat: add web search fallback`, update this file's Phase status table
   and commit log, then move to Phase 5.
