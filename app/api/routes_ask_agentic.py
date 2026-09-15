import asyncio
import logging
import time

from fastapi import APIRouter

from app.agentic.agent import run_agentic_answer
from app.core.config import Settings, get_settings
from app.core.dependencies import build_llm_client, build_retriever
from app.core.models import AskRequest, AskResponse
from app.core.tracing import new_run_id
from app.generation.evidence import build_evidence

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ask"])


def _ask_agentic_sync(request: AskRequest, settings: Settings) -> AskResponse:
    run_id = new_run_id()
    start = time.monotonic()
    logger.info("agentic run %s: question=%r", run_id, request.question)

    retriever = build_retriever(settings)
    llm = build_llm_client(settings)

    # Deliberately no grading/rewriting/quality-threshold pass here (contrast with
    # run_corrective_retrieval in app/correction/controller.py) -- the agent itself judges
    # whether this evidence is sufficient and decides whether to call web_search, rather than a
    # fixed pipeline branch deciding for it.
    retrieved = retriever.retrieve(request.question, top_k=settings.top_k)
    evidence = build_evidence(retrieved, max_context_chars=settings.max_context_chars)

    answer, sources, tool_trace = run_agentic_answer(request.question, evidence, llm, settings)
    latency = time.monotonic() - start
    logger.info("agentic run %s: completed in %.2fs, %d tool call(s)", run_id, latency, len(tool_trace))

    debug_info = None
    if request.debug:
        debug_info = {
            "run_id": run_id,
            "evidence": [e.model_dump() for e in evidence],
            "tool_calls": tool_trace,
            "latency_seconds": latency,
        }

    return AskResponse(
        run_id=run_id,
        answer=answer,
        sources=sources,
        retrieval_status="AGENTIC",
        grounding_status="NOT_VERIFIED",
        debug=debug_info,
    )


@router.post("/ask/agentic", response_model=AskResponse)
async def ask_agentic(request: AskRequest):
    """Alternate answer path to /ask: instead of the fixed grade -> rewrite -> web-fallback
    pipeline in app/correction/controller.py deciding when to search the web based on a
    retrieval-quality score, this endpoint hands the model a real web_search tool (OpenAI-style
    function calling) and lets the model itself decide, per question, whether local retrieval is
    enough or it needs to search. Requires an LLM provider whose LLMClient implements
    generate_with_tools -- OpenRouter and Groq do; Ollama does too, but tool-calling reliability
    on the project's default local model (llama3.2:3b) is noticeably weaker than on a larger
    hosted model (see README known limitations). request.web_fallback is unused here since the
    tool call *is* the fallback decision; grounding_status is always "NOT_VERIFIED" since this
    path skips the claim-verification pass /ask runs (see app/verification/verifier.py) -- an
    intentional scope cut, not an oversight, since running verification against a decision
    already produced by tool selection is unnecessarily two agentic steps for a comparison
    endpoint like this one."""
    settings = get_settings()
    return await asyncio.to_thread(_ask_agentic_sync, request, settings)
