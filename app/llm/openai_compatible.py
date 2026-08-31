import logging
import time

import httpx

from app.llm.base import LLMClient

logger = logging.getLogger(__name__)


class OpenAICompatibleClientError(Exception):
    pass


class OpenAICompatibleRateLimitError(OpenAICompatibleClientError):
    pass


class OpenAICompatibleClient(LLMClient):
    """Shared implementation for cloud providers exposing an OpenAI-compatible
    /chat/completions endpoint (OpenRouter, Groq, ...). Subclasses just declare `provider_name`,
    `api_url`, and `key_setup_hint`.

    Handles two failure modes discovered live while integrating the first such provider
    (OpenRouter): a 429 rate limit can arrive either as the HTTP status code, or embedded in an
    HTTP-200 response body (`{"error": {"code": 429, ...}}`) that `raise_for_status()` cannot
    see at all. Both are treated as retryable with exponential backoff, since this pipeline can
    make 5-15+ LLM calls for a single /ask request and hitting a shared free-tier rate limit
    partway through is an expected, common occurrence here, not a rare edge case."""

    provider_name = "provider"
    api_url = ""
    key_setup_hint = ""

    def __init__(self, api_key: str, model: str, timeout: float = 120.0, max_rate_limit_retries: int = 3):
        if not api_key:
            raise OpenAICompatibleClientError(f"{self.provider_name} API key is not set. {self.key_setup_hint}")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._max_rate_limit_retries = max_rate_limit_retries

    def _post_once(self, messages: list[dict], temperature: float) -> dict:
        try:
            response = httpx.post(
                self.api_url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"model": self._model, "messages": messages, "temperature": temperature},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise OpenAICompatibleRateLimitError(str(exc)) from exc
            raise OpenAICompatibleClientError(f"{self.provider_name} request failed: {exc}") from exc
        except httpx.HTTPError as exc:
            raise OpenAICompatibleClientError(f"{self.provider_name} request failed: {exc}") from exc

        data = response.json()

        if isinstance(data, dict) and "error" in data:
            error = data["error"]
            code = error.get("code") if isinstance(error, dict) else None
            if code == 429:
                raise OpenAICompatibleRateLimitError(str(error))
            raise OpenAICompatibleClientError(f"{self.provider_name} returned an error: {error}")

        return data

    def generate(self, prompt: str, system: str | None = None, temperature: float = 0.0) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        data = None
        last_error: OpenAICompatibleRateLimitError | None = None
        for attempt in range(self._max_rate_limit_retries + 1):
            try:
                data = self._post_once(messages, temperature)
                break
            except OpenAICompatibleRateLimitError as exc:
                last_error = exc
                if attempt < self._max_rate_limit_retries:
                    wait_seconds = 2**attempt
                    logger.warning(
                        "%s rate-limited (attempt %d/%d); retrying in %ds",
                        self.provider_name,
                        attempt + 1,
                        self._max_rate_limit_retries,
                        wait_seconds,
                    )
                    time.sleep(wait_seconds)

        if data is None:
            raise OpenAICompatibleClientError(
                f"{self.provider_name} request failed after retries: {last_error}"
            ) from last_error

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenAICompatibleClientError(f"Unexpected {self.provider_name} response shape: {data}") from exc
