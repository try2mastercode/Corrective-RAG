from app.llm.openai_compatible import (
    OpenAICompatibleClient,
    OpenAICompatibleClientError,
    OpenAICompatibleRateLimitError,
)

# Kept as aliases so existing imports/tests referencing these names keep working.
OpenRouterClientError = OpenAICompatibleClientError
OpenRouterRateLimitError = OpenAICompatibleRateLimitError


class OpenRouterClient(OpenAICompatibleClient):
    """OpenRouter is a cloud-hosted, OpenAI-API-compatible aggregator giving access to many
    models (including free-tier ones) behind a single API key. Using it means questions and
    document content leave the local machine -- this project's default is the local Ollama
    client; this provider exists only because the user explicitly chose to opt into a cloud
    provider, overriding the project's own local-first default."""

    provider_name = "OpenRouter"
    api_url = "https://openrouter.ai/api/v1/chat/completions"
    key_setup_hint = "Get a free key at https://openrouter.ai/keys and set OPENROUTER_API_KEY in .env."
