import logging

from app.core.models import QueryRewrite
from app.llm.base import LLMClient
from app.llm.retry import generate_parsed

logger = logging.getLogger(__name__)

QUERY_REWRITER_SYSTEM_PROMPT_V1 = """\
You are a query rewriting assistant for a document retrieval system.

The user's question did not retrieve strong results. Rewrite it to improve retrieval by:
- expanding abbreviations
- adding specific keywords implied by the question
- clarifying ambiguous wording

Rules:
1. Preserve the original intent and meaning exactly.
2. Do not invent facts, entities, or assumptions not implied by the original question.
3. Do not answer the question.

Return JSON only, with exactly these keys and no other text:
{"rewritten_query": "...", "reason": "brief explanation of what was changed and why"}
"""


def _build_rewrite_prompt(question: str) -> str:
    return f"Original question:\n{question}\n\nReturn JSON only."


def _parse_rewrite(raw: dict, original_query: str) -> QueryRewrite | None:
    try:
        rewritten = str(raw["rewritten_query"]).strip()
        reason = str(raw.get("reason", ""))
    except (KeyError, TypeError):
        return None

    if not rewritten:
        return None

    return QueryRewrite(original_query=original_query, rewritten_query=rewritten, reason=reason)


def rewrite_query(question: str, llm: LLMClient, max_retries: int = 2) -> QueryRewrite:
    prompt = _build_rewrite_prompt(question)
    rewrite = generate_parsed(
        llm, prompt, QUERY_REWRITER_SYSTEM_PROMPT_V1, lambda raw: _parse_rewrite(raw, question), max_retries
    )

    if rewrite is not None:
        logger.info("query rewrite: %r -> %r", question, rewrite.rewritten_query)
        return rewrite

    logger.error("query rewriter failed after %d attempts; falling back to original query", max_retries + 1)
    return QueryRewrite(
        original_query=question,
        rewritten_query=question,
        reason="Rewrite failed after retries; using the original query unchanged.",
    )
