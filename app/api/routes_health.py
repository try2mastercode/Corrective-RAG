import httpx
from fastapi import APIRouter

from app.core.config import Settings, get_settings

router = APIRouter()

# provider -> (models endpoint for a reachability check, api_key attr, model attr)
_CLOUD_PROVIDERS = {
    "openrouter": ("https://openrouter.ai/api/v1/models", "openrouter_api_key", "openrouter_model"),
    "groq": ("https://api.groq.com/openai/v1/models", "groq_api_key", "groq_model"),
}


async def _check_cloud_provider(models_url: str, api_key: str) -> str:
    if not api_key:
        return "missing_api_key"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(models_url, headers={"Authorization": f"Bearer {api_key}"})
            return "reachable" if resp.status_code == 200 else "unreachable"
    except httpx.HTTPError:
        return "unreachable"


async def _check_ollama(settings: Settings) -> str:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{settings.llm_base_url}/api/tags")
            return "reachable" if resp.status_code == 200 else "unreachable"
    except httpx.HTTPError:
        return "unreachable"


@router.get("/health")
async def health() -> dict:
    settings = get_settings()

    if settings.llm_provider in _CLOUD_PROVIDERS:
        models_url, api_key_attr, model_attr = _CLOUD_PROVIDERS[settings.llm_provider]
        llm_model = getattr(settings, model_attr)
        llm_status = await _check_cloud_provider(models_url, getattr(settings, api_key_attr))
    else:
        llm_model = settings.llm_model
        llm_status = await _check_ollama(settings)

    return {
        "status": "ok",
        "app_env": settings.app_env,
        "llm_provider": settings.llm_provider,
        "llm_model": llm_model,
        "llm_status": llm_status,
    }
