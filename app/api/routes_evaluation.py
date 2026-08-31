import asyncio

from fastapi import APIRouter

from app.core.config import Settings, get_settings
from app.evaluation.dataset import load_dataset
from app.evaluation.ragas_runner import run_ragas_evaluation
from app.evaluation.reports import build_report
from app.evaluation.runners import run_baseline, run_crag

router = APIRouter(tags=["evaluation"])


def _evaluate_sync(
    dataset_path: str,
    limit: int | None,
    web_fallback: bool,
    include_ragas: bool,
    settings: Settings,
) -> dict:
    questions = load_dataset(dataset_path)
    if limit:
        questions = questions[:limit]

    baseline_records = [run_baseline(q, settings) for q in questions]
    crag_records = [run_crag(q, settings, web_fallback=web_fallback) for q in questions]

    baseline_ragas: dict = {}
    crag_ragas: dict = {}
    if include_ragas:
        baseline_ragas = run_ragas_evaluation(baseline_records, settings)
        crag_ragas = run_ragas_evaluation(crag_records, settings)

    return build_report(baseline_records, crag_records, baseline_ragas, crag_ragas)


@router.post("/evaluate")
async def evaluate(
    dataset_path: str = "data/evaluation/dataset.json",
    limit: int | None = None,
    web_fallback: bool = False,
    include_ragas: bool = True,
):
    """Run the baseline-vs-CRAG evaluation and return the comparison report. This can take a
    long time for a full dataset (each question runs the full pipeline, plus RAGAS's own
    judge-model calls) -- pass a small `limit` for interactive testing; use `scripts/evaluate.py`
    for a full unattended run against a corpus you've indexed separately."""
    settings = get_settings()
    # Every question runs a fully synchronous pipeline (embedding inference, blocking Ollama
    # calls, RAGAS's own judge-model calls) -- offload to a worker thread so this long-running
    # request doesn't block other concurrent requests on the event loop.
    return await asyncio.to_thread(_evaluate_sync, dataset_path, limit, web_fallback, include_ragas, settings)
