import time

from pydantic import BaseModel

from app.core.config import Settings
from app.core.dependencies import build_llm_client, build_retriever
from app.core.models import VerificationOutcome, VerificationResult
from app.correction.controller import apply_web_fallback, compute_retrieval_status, run_corrective_retrieval
from app.evaluation.dataset import EvalQuestion
from app.generation.answer import generate_answer
from app.generation.evidence import build_evidence
from app.verification.verifier import verify_and_correct_answer


class RunRecord(BaseModel):
    question_id: str
    category: str
    question: str
    ground_truth: str
    answer: str
    contexts: list[str]
    latency_seconds: float
    retrieval_status: str | None = None
    grounding_status: str | None = None
    retrieval_rounds: int = 1
    rewrite_used: bool = False
    web_used: bool = False
    answer_corrected: bool = False


def run_baseline(question: EvalQuestion, settings: Settings) -> RunRecord:
    """Question -> retrieve -> generate. No grading, no correction, no verification -- the
    simplest possible RAG pipeline, used as the comparison point for CRAG."""
    retriever = build_retriever(settings)
    llm = build_llm_client(settings)

    start = time.monotonic()
    chunks = retriever.retrieve(question.question, top_k=settings.top_k)
    evidence = build_evidence(chunks, max_context_chars=settings.max_context_chars)
    answer, _sources = generate_answer(question.question, evidence, llm)
    latency = time.monotonic() - start

    return RunRecord(
        question_id=question.id,
        category=question.category,
        question=question.question,
        ground_truth=question.ground_truth,
        answer=answer,
        contexts=[e.text for e in evidence],
        latency_seconds=latency,
    )


def run_crag(question: EvalQuestion, settings: Settings, web_fallback: bool = False) -> RunRecord:
    """Question -> retrieve -> grade -> correct if weak -> web fallback if still weak and
    enabled -> generate -> verify -> correct answer if needed. The full pipeline built in
    Phases 1-6."""
    retriever = build_retriever(settings)
    llm = build_llm_client(settings)

    start = time.monotonic()
    correction = run_corrective_retrieval(question.question, retriever, llm, settings)

    if web_fallback:
        correction = apply_web_fallback(question.question, correction, llm, settings)

    evidence = build_evidence(correction.final_chunks, max_context_chars=settings.max_context_chars)
    draft_answer, _sources = generate_answer(question.question, evidence, llm)

    if not evidence:
        outcome = VerificationOutcome(
            final_answer=draft_answer,
            verification=VerificationResult(claims=[], grounding_score=1.0, status="SUPPORTED"),
            corrected=False,
            correction_attempts=0,
        )
    else:
        outcome = verify_and_correct_answer(question.question, evidence, draft_answer, llm, settings)

    latency = time.monotonic() - start

    return RunRecord(
        question_id=question.id,
        category=question.category,
        question=question.question,
        ground_truth=question.ground_truth,
        answer=outcome.final_answer,
        contexts=[e.text for e in evidence],
        latency_seconds=latency,
        retrieval_status=compute_retrieval_status(evidence, correction),
        grounding_status=outcome.verification.status,
        retrieval_rounds=len(correction.rounds),
        rewrite_used=len(correction.rewrites) > 0,
        web_used=correction.web_used,
        answer_corrected=outcome.corrected,
    )
