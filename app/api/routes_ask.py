from fastapi import APIRouter

from app.core.config import get_settings
from app.core.dependencies import build_llm_client, build_retriever
from app.core.models import AskRequest, AskResponse, RetrieveResponse
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

    chunks = retriever.retrieve(request.question, top_k=settings.top_k)
    answer, sources = generate_answer(request.question, chunks, llm)

    retrieval_status = "OK" if chunks else "NO_RESULTS"
    return AskResponse(answer=answer, sources=sources, retrieval_status=retrieval_status)
