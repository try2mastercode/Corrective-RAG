import httpx

from app.llm.base import LLMClient

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterClientError(Exception):
    pass


class OpenRouterClient(LLMClient):
    """OpenRouter is a cloud-hosted, OpenAI-API-compatible aggregator giving access to many
    models (including free-tier ones) behind a single API key. Using it means questions and
    document content leave the local machine -- this project's default is the local Ollama
    client; this provider exists only because the user explicitly chose to opt into a cloud
    provider, overriding the project's own local-first default."""

    def __init__(self, api_key: str, model: str, timeout: float = 120.0):
        if not api_key:
            raise OpenRouterClientError(
                "OPENROUTER_API_KEY is not set. Get a free key at https://openrouter.ai/keys "
                "and set it in .env."
            )
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def generate(self, prompt: str, system: str | None = None, temperature: float = 0.0) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = httpx.post(
                OPENROUTER_API_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"model": self._model, "messages": messages, "temperature": temperature},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OpenRouterClientError(f"OpenRouter request failed: {exc}") from exc

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenRouterClientError(f"Unexpected OpenRouter response shape: {data}") from exc
