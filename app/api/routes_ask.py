import asyncio
import logging
import time

from fastapi import APIRouter

from app.core.config import Settings, get_settings
from app.core.dependencies import build_llm_client, build_retriever
from app.core.models import AskRequest, AskResponse, RetrieveResponse, VerificationOutcome, VerificationResult
from app.core.tracing import _build_run_trace, new_run_id, record_run
from app.correction.controller import apply_web_fallback, compute_retrieval_status, run_corrective_retrieval
from app.generation.answer import generate_answer
from app.generation.evidence import build_evidence
from app.verification.verifier import verify_and_correct_answer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ask"])


def _retrieve_sync(query: str, settings: Settings) -> RetrieveResponse:
    retriever = build_retriever(settings)
    results = retriever.retrieve(query, top_k=settings.top_k)
    return RetrieveResponse(query=query, results=results)


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(query: str):
    # Embedding inference and the Chroma query are synchronous, CPU-bound/blocking calls --
    # running them directly in this async def would block the whole event loop (and every other
    # concurrent request, including /health) for their duration. Offload to a worker thread.
    settings = get_settings()
    return await asyncio.to_thread(_retrieve_sync, query, settings)


def _ask_sync(request: AskRequest, settings: Settings) -> AskResponse:
    run_id = new_run_id()
    start = time.monotonic()
    logger.info("run %s: question=%r web_fallback=%s", run_id, request.question, request.web_fallback)

    retriever = build_retriever(settings)
    llm = build_llm_client(settings)

    correction = run_corrective_retrieval(request.question, retriever, llm, settings)

    if request.web_fallback:
        correction = apply_web_fallback(request.question, correction, llm, settings)

    evidence = build_evidence(correction.final_chunks, max_context_chars=settings.max_context_chars)
    draft_answer, sources = generate_answer(request.question, evidence, llm)

    if not evidence:
        # Nothing was generated beyond the canned "insufficient evidence" message -- nothing to
        # verify, and skipping it saves a wasted LLM round trip on the common no-evidence path.
        outcome = VerificationOutcome(
            final_answer=draft_answer,
            verification=VerificationResult(claims=[], grounding_score=1.0, status="SUPPORTED"),
            corrected=False,
            correction_attempts=0,
        )
    else:
        outcome = verify_and_correct_answer(request.question, evidence, draft_answer, llm, settings)

    retrieval_status = compute_retrieval_status(evidence, correction)
    latency = time.monotonic() - start
    final_status = f"{retrieval_status}/{outcome.verification.status}"

    record_run(
        _build_run_trace(run_id, request.question, correction, evidence, outcome, latency, final_status)
    )
    logger.info("run %s: completed in %.2fs status=%s", run_id, latency, final_status)

    debug_info = None
    if request.debug:
        debug_info = {
            "run_id": run_id,
            "rounds": [r.model_dump() for r in correction.rounds],
            "rewrites": [r.model_dump() for r in correction.rewrites],
            "final_quality": correction.final_quality.model_dump(),
            "evidence": [e.model_dump() for e in evidence],
            "web_search_triggered": correction.web_search_triggered,
            "web_used": correction.web_used,
            "web_results": [r.model_dump() for r in correction.web_results],
            "draft_answer": draft_answer,
            "verification": outcome.verification.model_dump(),
            "answer_corrected": outcome.corrected,
            "correction_attempts": outcome.correction_attempts,
            "gave_up_on_correction": outcome.gave_up,
            "latency_seconds": latency,
        }

    return AskResponse(
        run_id=run_id,
        answer=outcome.final_answer,
        sources=sources,
        retrieval_status=retrieval_status,
        grounding_status=outcome.verification.status,
        debug=debug_info,
    )


@router.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest):
    # The full CRAG pipeline (retrieval, grading, rewriting, web search, generation,
    # verification) is built from synchronous calls -- CPU-bound embedding inference and
    # blocking HTTP calls to Ollama. Run it in a worker thread so a single slow /ask (which can
    # take tens of seconds) doesn't block every other concurrent request on this server.
    settings = get_settings()
    return await asyncio.to_thread(_ask_sync, request, settings)
