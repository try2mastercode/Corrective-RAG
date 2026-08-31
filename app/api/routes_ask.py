from fastapi import APIRouter

from app.core.config import get_settings
from app.core.dependencies import build_llm_client, build_retriever
from app.core.models import AskRequest, AskResponse, RetrieveResponse, VerificationOutcome, VerificationResult
from app.correction.controller import apply_web_fallback, compute_retrieval_status, run_corrective_retrieval
from app.generation.answer import generate_answer
from app.generation.evidence import build_evidence
from app.verification.verifier import verify_and_correct_answer

router = APIRouter(tags=["ask"])


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(query: str):
    settings = get_settings()
    retriever = build_retriever(settings)
    results = retriever.retrieve(query, top_k=settings.top_k)
    return RetrieveResponse(query=query, results=results)


@router.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest):
    settings = get_settings()
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

    debug_info = None
    if request.debug:
        debug_info = {
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
        }

    return AskResponse(
        answer=outcome.final_answer,
        sources=sources,
        retrieval_status=retrieval_status,
        grounding_status=outcome.verification.status,
        debug=debug_info,
    )
