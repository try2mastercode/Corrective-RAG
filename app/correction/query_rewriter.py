import json
import logging
import re

from app.core.models import QueryRewrite
from app.llm.base import LLMClient

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


def _extract_json(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


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

    for attempt in range(max_retries + 1):
        raw_output = llm.generate(prompt, system=QUERY_REWRITER_SYSTEM_PROMPT_V1, temperature=0.0)
        parsed = _extract_json(raw_output)
        rewrite = _parse_rewrite(parsed, question) if parsed else None

        if rewrite is not None:
            logger.info("query rewrite: %r -> %r", question, rewrite.rewritten_query)
            return rewrite

        logger.warning("malformed rewrite output on attempt %d: %r", attempt + 1, raw_output)

    logger.error("query rewriter failed after %d attempts; falling back to original query", max_retries + 1)
    return QueryRewrite(
        original_query=question,
        rewritten_query=question,
        reason="Rewrite failed after retries; using the original query unchanged.",
    )
