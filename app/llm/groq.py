from app.llm.openai_compatible import (
    OpenAICompatibleClient,
    OpenAICompatibleClientError,
    OpenAICompatibleRateLimitError,
)

# Aliases so callers can import a Groq-specific name, consistent with the OpenRouter module.
GroqClientError = OpenAICompatibleClientError
GroqRateLimitError = OpenAICompatibleRateLimitError


class GroqClient(OpenAICompatibleClient):
    """Groq is a cloud-hosted, OpenAI-API-compatible provider running models on custom hardware
    (LPUs), giving notably lower per-call latency than typical cloud LLM APIs. Its free tier is
    also per-account (not a pool shared with every other free user, unlike OpenRouter's free
    models), giving substantially more daily headroom for a pipeline that makes many calls per
    question. Using it still means questions and document content leave the local machine --
    this project's default is the local Ollama client; this provider exists only because the
    user explicitly chose to opt into a cloud provider, overriding the project's own
    local-first default."""

    provider_name = "Groq"
    api_url = "https://api.groq.com/openai/v1/chat/completions"
    key_setup_hint = "Get a free key at https://console.groq.com/keys and set GROQ_API_KEY in .env."
