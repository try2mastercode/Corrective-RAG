import logging
import time

import httpx

from app.llm.base import LLMClient

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterClientError(Exception):
    pass


class OpenRouterRateLimitError(OpenRouterClientError):
    pass


class OpenRouterClient(LLMClient):
    """OpenRouter is a cloud-hosted, OpenAI-API-compatible aggregator giving access to many
    models (including free-tier ones) behind a single API key. Using it means questions and
    document content leave the local machine -- this project's default is the local Ollama
    client; this provider exists only because the user explicitly chose to opt into a cloud
    provider, overriding the project's own local-first default."""

    def __init__(self, api_key: str, model: str, timeout: float = 120.0, max_rate_limit_retries: int = 3):
        if not api_key:
            raise OpenRouterClientError(
                "OPENROUTER_API_KEY is not set. Get a free key at https://openrouter.ai/keys "
                "and set it in .env."
            )
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._max_rate_limit_retries = max_rate_limit_retries

    def _post_once(self, messages: list[dict], temperature: float) -> dict:
        try:
            response = httpx.post(
                OPENROUTER_API_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"model": self._model, "messages": messages, "temperature": temperature},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise OpenRouterRateLimitError(str(exc)) from exc
            raise OpenRouterClientError(f"OpenRouter request failed: {exc}") from exc
        except httpx.HTTPError as exc:
            raise OpenRouterClientError(f"OpenRouter request failed: {exc}") from exc

        data = response.json()

        # OpenRouter sometimes returns HTTP 200 with the actual failure embedded in the JSON
        # body instead of the HTTP status -- e.g. {"error": {"code": 429, ...}} -- which
        # raise_for_status() above cannot see at all since the transport-level status was fine.
        if isinstance(data, dict) and "error" in data:
            error = data["error"]
            code = error.get("code") if isinstance(error, dict) else None
            if code == 429:
                raise OpenRouterRateLimitError(str(error))
            raise OpenRouterClientError(f"OpenRouter returned an error: {error}")

        return data

    def generate(self, prompt: str, system: str | None = None, temperature: float = 0.0) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # This pipeline can make 5-15+ LLM calls for a single /ask request (grading, rewriting,
        # claim extraction, per-claim verification) -- free-tier rate limits on a shared model
        # pool are hit far more easily here than with a single-call chatbot, so a rate limit
        # (whether signaled via HTTP 429 or embedded in a 200 response body) needs to be treated
        # as a normal, expected, retryable condition rather than a fatal error.
        data = None
        last_error: OpenRouterRateLimitError | None = None
        for attempt in range(self._max_rate_limit_retries + 1):
            try:
                data = self._post_once(messages, temperature)
                break
            except OpenRouterRateLimitError as exc:
                last_error = exc
                if attempt < self._max_rate_limit_retries:
                    wait_seconds = 2**attempt
                    logger.warning(
                        "OpenRouter rate-limited (attempt %d/%d); retrying in %ds",
                        attempt + 1,
                        self._max_rate_limit_retries,
                        wait_seconds,
                    )
                    time.sleep(wait_seconds)

        if data is None:
            raise OpenRouterClientError(f"OpenRouter request failed after retries: {last_error}") from last_error

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenRouterClientError(f"Unexpected OpenRouter response shape: {data}") from exc
