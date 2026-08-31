from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.core.tracing import all_runs, get_run

router = APIRouter(tags=["observability"])


@router.get("/config")
async def get_config():
    data = get_settings().model_dump()
    data.pop("web_search_api_key", None)  # never expose secrets, even when empty
    return data


@router.get("/runs/{run_id}")
async def get_run_trace(run_id: str):
    trace = get_run(run_id)
    if trace is None:
        raise HTTPException(
            status_code=404,
            detail="Run not found. The trace store is in-memory only (not persisted across "
            "restarts) and keeps only the most recent runs.",
        )
    return trace


@router.get("/metrics")
async def get_metrics():
    runs = all_runs()
    if not runs:
        return {"total_runs": 0}

    latencies = [r.generation_latency_seconds for r in runs]
    return {
        "total_runs": len(runs),
        "avg_latency_seconds": sum(latencies) / len(latencies),
        "rewrite_rate": sum(1 for r in runs if r.rewritten_queries) / len(runs),
        "web_fallback_rate": sum(1 for r in runs if r.web_used) / len(runs),
        "avg_grounding_score": sum(r.verification_grounding_score for r in runs) / len(runs),
    }
