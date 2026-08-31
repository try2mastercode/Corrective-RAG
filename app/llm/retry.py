import logging
from typing import Callable, TypeVar

from app.llm.base import LLMClient
from app.llm.json_utils import extract_json

logger = logging.getLogger(__name__)

T = TypeVar("T")


def generate_parsed(
    llm: LLMClient,
    prompt: str,
    system: str,
    parse_fn: Callable[[dict], T | None],
    max_retries: int = 2,
    temperature: float = 0.0,
) -> T | None:
    """Shared shape for every "call the LLM, extract JSON, parse it, retry on malformed output"
    loop in this codebase (grading, query rewriting, claim extraction, claim verification).
    Returns None once retries are exhausted -- callers supply their own safe-default fallback
    and success logging, since those are meaningfully different per call site."""
    for attempt in range(max_retries + 1):
        raw_output = llm.generate(prompt, system=system, temperature=temperature)
        parsed = extract_json(raw_output)
        result = parse_fn(parsed) if parsed is not None else None

        if result is not None:
            return result

        logger.warning("malformed structured output on attempt %d: %r", attempt + 1, raw_output)

    return None
