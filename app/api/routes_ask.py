from fastapi import APIRouter

from app.core.config import get_settings
from app.core.dependencies import build_llm_client, build_retriever
from app.core.models import AskRequest, AskResponse, RetrieveResponse
from app.correction.controller import apply_web_fallback, run_corrective_retrieval
from app.generation.answer import generate_answer

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

    answer, sources = generate_answer(request.question, correction.final_chunks, llm)

    if not correction.final_chunks:
        retrieval_status = "NO_RESULTS"
    elif correction.web_used:
        retrieval_status = "WEB_FALLBACK"
    else:
        retrieval_status = correction.final_quality.decision

    debug_info = None
    if request.debug:
        debug_info = {
            "rounds": [r.model_dump() for r in correction.rounds],
            "rewrites": [r.model_dump() for r in correction.rewrites],
            "final_quality": correction.final_quality.model_dump(),
            "final_chunk_ids": [c.chunk_id for c in correction.final_chunks],
            "web_search_triggered": correction.web_search_triggered,
            "web_used": correction.web_used,
            "web_results": [r.model_dump() for r in correction.web_results],
        }

    return AskResponse(answer=answer, sources=sources, retrieval_status=retrieval_status, debug=debug_info)
