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
| Web search | DuckDuckGo via the `ddgs` package, no API key | Decided 2026-08-31 when Phase 4 started. Free, no signup. See Phase 4 detail below for adapter design. |
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
before committing. That held through Phases 2-3. On 2026-08-31 the user said to go through all
remaining phases (4 onward) without needing them for each one. From Phase 4 onward: implement,
test, commit, and move to the next phase autonomously — only stop for a genuine blocker (a
decision only the user can make, like an API key or an ambiguous spec choice affecting
direction), not for routine "may I commit?" checkpoints.

## Phase status

- [x] **Phase 0** — Repository and Local Environment — DONE (commit `cee5874`)
- [x] **Phase 1** — Basic Local RAG — DONE (commits `044a77f`, `d632782`)
- [x] **Phase 2** — Retrieval Grading — DONE (commit `f5e748a`)
- [x] **Phase 3** — Corrective Query Rewriting and Re-Retrieval — DONE (commit `b7380b9`)
- [x] **Phase 4** — Web Search Fallback — DONE (commit `0fe03ca`)
- [x] **Phase 5** — Evidence Builder and Grounded Generation — DONE (commit `3813458`)
- [ ] **Phase 6** — Hallucination / Claim Verification — IN PROGRESS
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
| 3 | `b7380b9` | feat: add corrective query rewriting |
| 4 | `0fe03ca` | feat: add web search fallback |
| 5 | `3813458` | feat: add grounded evidence generation |

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

## Completed phase detail — Phase 4 (Web Search Fallback)

All checklist items done. Verified via `pytest` (55 passed — 18 new: 7 web-search adapter unit
tests using a fake DDGS double, no real network calls in the test suite; 6 new
`apply_web_fallback` controller tests) and a live end-to-end smoke test against real DuckDuckGo
+ Ollama/`llama3.2:3b`: indexed an unrelated local document (canal towpath resurfacing), asked
"What year did the first iPhone get released?" with `web_fallback: true` — local retrieval
correctly graded LOW on both rounds (rewrite attempted, still LOW — the answer genuinely isn't
local), web fallback triggered, fetched 5 real Wikipedia/tech-site results, graded them, and the
final answer correctly said "2007" citing `[2]`/`[3]` as sources, all five sources labeled
`source_type: "WEB_SOURCE"`, and `retrieval_status: "WEB_FALLBACK"`.

Key artifacts added:
- `app/web/search.py` — `web_search(query, provider, max_results, timeout)`, currently
  implementing `"duckduckgo"` via the `ddgs` package (successor to the now-legacy
  `duckduckgo-search` package; no API key/signup needed). Catches `DDGSException` and any other
  unexpected exception, always degrading to `[]` rather than raising — a search failure must
  never crash `/ask`. Deduplicates by URL. Unknown/unconfigured provider also degrades to `[]`
  with a warning log (so `WEB_SEARCH_PROVIDER` can be extended later without touching call sites)
- `app/correction/controller.py` — `apply_web_fallback(question, correction, llm, settings)`:
  triggers only when `settings.web_search_enabled` AND the local `final_quality.decision` is not
  already `HIGH` (both gates independent of the per-request `AskRequest.web_fallback` flag, which
  is the *third* gate checked at the route level — all three must be true). Web results are
  converted to `RetrievedChunk` (`source_type="WEB_SOURCE"`, a neutral placeholder `score=0.5`
  since vector-similarity scoring doesn't apply to web search hits), graded with the *same*
  `grade_chunks` used for local evidence (against the original question, consistent with the
  Phase 3 pattern), and only non-`IRRELEVANT` results are appended **after** existing local
  chunks — local evidence is never displaced by web evidence, only supplemented
- `app/core/models.py` — `WebSearchResult`; `RetrievedChunk` gained `source_type` (default
  `"LOCAL_DOCUMENT"`); `SourceCitation` gained `source_type`; `CorrectiveRetrievalResult` gained
  `web_search_triggered` / `web_used` / `web_results` for full debug transparency (triggered vs.
  actually-used are tracked separately, so a fetch-succeeded-but-all-irrelevant case is
  distinguishable from a fetch-failed case)
- `app/generation/prompts.py` / `answer.py` — the evidence block shown to the LLM now labels
  each passage `(local document: ...)` or `(web source: ...)` inline, satisfying todo.md section
  13's "must never silently imply a web result came from local database" at the prompt level, not
  just in the API response
- `app/api/routes_ask.py` — `/ask` calls `apply_web_fallback` only when `request.web_fallback` is
  true; `retrieval_status` becomes `"WEB_FALLBACK"` when web evidence was actually incorporated,
  otherwise unchanged from Phase 2/3's HIGH/MEDIUM/LOW/NO_RESULTS
- `tests/unit/test_web_search.py`, plus additions to `tests/unit/test_controller.py`

**Design decision worth remembering:** `CorrectiveRetrievalResult.final_quality` deliberately
stays a **local-only** metric even after web fallback runs (it is not recomputed/blended with web
results) — the live smoke test above shows `final_quality.decision: "LOW"` even though the
answer was fully and correctly grounded in good web evidence. The user-facing `retrieval_status`
field is what reflects reality (it becomes `"WEB_FALLBACK"`), computed at the route level. This
was a deliberate choice, not an oversight: building a unified cross-source quality/ranking model
(blending vector-similarity scores with web search rank) is explicitly Phase 5's job per todo.md
section 14 ("Evidence Builder... Rank evidence by relevance"), so Phase 4 intentionally leaves
that unsolved rather than reaching ahead into Phase 5's scope.

Known limitations / deliberate scope boundaries:
- No formal Evidence Builder yet — evidence IDs shown to the user are just the final list order
  (`[1]`, `[2]`, ...), not stable IDs assigned once and carried through generation +
  verification. That stability guarantee is explicitly Phase 5's job (todo.md section 14: "Keep
  evidence IDs stable through answer generation").
- No claim verification / hallucination check yet (Phase 6) — nothing double-checks that the
  answer's claims are actually supported by the (now possibly web-sourced) evidence beyond the
  existing grading-based filtering.
- Web search adds real latency (network + up to `WEB_SEARCH_MAX_RESULTS` grading calls) only when
  triggered (disabled by default, and gated by both the global flag and the per-request opt-in),
  so it doesn't affect the default `/ask` path at all.

## Completed phase detail — Phase 5 (Evidence Builder and Grounded Generation)

All checklist items done. Verified via `pytest` (65 passed — 10 new: 6 evidence-builder unit
tests, 4 generation-layer unit tests) and a live smoke test against real Ollama/`llama3.2:3b`:
indexed a document, asked a question, and confirmed the response's `sources[0].id` is now
`"E1"` (matching todo.md section 24's example response format exactly, replacing the plain `"1"`
positional index used since Phase 1), and the `/ask` debug payload exposes the full built
evidence layer (id, type, source, location, page, text) distinct from the raw grading/round
diagnostics already there.

Key artifacts added:
- `app/generation/evidence.py` — `build_evidence(chunks, max_context_chars)`: assigns stable
  `E1`/`E2`/... IDs once, dedups near-identical passages (whitespace/case-normalized text
  equality — catches accidental repeats across local+web sources without a heavier NLP
  dependency), and caps total evidence text against `MAX_CONTEXT_CHARS` (default 8000, stops
  adding evidence once the budget is exceeded, but always keeps at least one item even if that
  single item alone exceeds the budget, so evidence is never dropped down to zero purely because
  of a small size cap)
- `app/core/models.py` — new `Evidence` model (`id`, `type`, `source`, `location`, `page`, `text`)
- `app/generation/prompts.py` / `answer.py` — `build_answer_prompt` and `generate_answer` now
  take `list[Evidence]` instead of `list[RetrievedChunk]`; prompt citation markers are `[E1]`,
  `[E2]` (was positional `[1]`, `[2]`); `SourceCitation.id` now comes directly from
  `Evidence.id`
- `app/api/routes_ask.py` — `/ask` now runs `build_evidence()` between correction (+ optional
  web fallback) and generation; `debug: true` exposes the evidence layer directly
- `tests/unit/test_evidence.py`, `tests/unit/test_generation.py`; updated
  `tests/integration/test_ask_pipeline.py` to build evidence before calling `generate_answer`
  (its signature changed)

**Documented, deliberate scope boundary (not a gap to "fix" later without reconsidering):**
evidence ranking is **not** re-computed here — `build_evidence` preserves whatever order the
correction controller already produced (local chunks sorted by grader score, then any web
fallback results appended after, sorted by their own grader score). A true unified cross-source
ranking would need a principled way to compare vector-similarity scores against web-search
relevance against grader confidence, which none of Phases 2-4 attempted to solve either — see
the "Design decision worth remembering" note under Phase 4. This stays an open question for
Phase 9 (or a documented limitation in the final README) rather than something to hack together
under time pressure now.

Known limitations / deliberate scope boundaries:
- No claim verification / hallucination check yet (Phase 6) — the answer generator still just
  trusts its own grounding to the supplied evidence; nothing double-checks the *output* claims
  against that evidence after the fact.
- No formal `ANSWERABLE` / `ANSWERABLE_WITH_CAVEAT` / `INSUFFICIENT_EVIDENCE` decision enum
  (todo.md section 18) — the existing `retrieval_status` (HIGH/MEDIUM/LOW/WEB_FALLBACK/
  NO_RESULTS) plus `generate_answer`'s empty-evidence fallback string cover the same practical
  ground today; the formal decision layer fits naturally alongside Phase 6's grounding score.

## Current phase detail — Phase 6 (Hallucination / Claim Verification) — in progress

Scope (from todo.md section 38 / section 16-17):
- [ ] Claim extraction (`app/verification/claims.py`) — LLM call that splits a generated answer
  into discrete factual claims
- [ ] Claim-to-evidence matching / support grading (`app/verification/verifier.py`) — for each
  claim, does the evidence actually support it? Structured output per todo.md section 16:
  `{claim, supported, evidence_ids, confidence}`
- [ ] Answer grounding score (aggregate over all claims) compared against
  `ANSWER_GROUNDING_THRESHOLD` (already in config, unused so far)
- [ ] Unsupported-claim detection feeding into...
- [ ] Answer correction loop (`app/verification/correction.py`) — regenerate/qualify/remove
  unsupported claims, bounded by `MAX_ANSWER_CORRECTIONS` (already in config, unused so far)
- [ ] Final verification pass after correction
- [ ] Insufficient-evidence fallback if grounding remains poor after max correction attempts
- [ ] Adversarial hallucination tests (deliberately trigger an unsupported claim and confirm it
  gets caught)
- [ ] Wire into `/ask`: generate -> verify -> correct if needed -> verify again -> final answer
- [ ] Expose verification results in `/ask` debug output; add a `grounding_status` field to
  `AskResponse` per todo.md section 24's example response shape (`"grounding_status": "SUPPORTED"`)

Acceptance criteria: when a generated answer contains an unsupported factual claim, the system
detects it and either removes/qualifies it or returns an insufficient-evidence response.

### Next action when resuming
1. Re-read this file top to bottom, then skim `todo.md` sections 16-17.
2. Continue autonomously per the standing instruction (implement, test, commit, move on) unless
   something is genuinely ambiguous.
3. Implement the checklist above, run tests (including at least one adversarial test that
   fabricates an unsupported claim and confirms it's caught), do a live smoke test, review
   `git diff`, commit as `feat: add hallucination verification`, update this file's Phase status
   table and commit log, then move to Phase 7.
