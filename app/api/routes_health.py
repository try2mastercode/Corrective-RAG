import httpx
from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    settings = get_settings()

    llm_status = "unknown"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{settings.llm_base_url}/api/tags")
            llm_status = "reachable" if resp.status_code == 200 else "unreachable"
    except httpx.HTTPError:
        llm_status = "unreachable"

    return {
        "status": "ok",
        "app_env": settings.app_env,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "llm_status": llm_status,
    }
