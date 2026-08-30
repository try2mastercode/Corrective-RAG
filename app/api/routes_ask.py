from fastapi import APIRouter

from app.core.config import get_settings
from app.core.dependencies import build_llm_client, build_retriever
from app.core.models import AskRequest, AskResponse, RetrieveResponse
from app.generation.answer import generate_answer
from app.retrieval.grader import calculate_retrieval_quality, grade_chunks

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

    chunks = retriever.retrieve(request.question, top_k=settings.top_k)
    answer, sources = generate_answer(request.question, chunks, llm)

    debug_info = None
    if not chunks:
        retrieval_status = "NO_RESULTS"
    else:
        graded = grade_chunks(request.question, chunks, llm, max_retries=settings.grader_max_retries)
        quality = calculate_retrieval_quality(
            graded,
            weight_mean=settings.quality_weight_mean,
            weight_best=settings.quality_weight_best,
            weight_relevant_ratio=settings.quality_weight_relevant_ratio,
            high_threshold=settings.retrieval_quality_high_threshold,
            medium_threshold=settings.retrieval_quality_medium_threshold,
        )
        retrieval_status = quality.decision

        if request.debug:
            debug_info = {
                "grades": [
                    {
                        "chunk_id": gc.chunk.chunk_id,
                        "score": gc.grade.score,
                        "label": gc.grade.label,
                        "reason": gc.grade.reason,
                    }
                    for gc in graded
                ],
                "quality": quality.model_dump(),
            }

    return AskResponse(answer=answer, sources=sources, retrieval_status=retrieval_status, debug=debug_info)
