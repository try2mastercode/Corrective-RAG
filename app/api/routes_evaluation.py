from fastapi import APIRouter

from app.core.config import get_settings
from app.evaluation.dataset import load_dataset
from app.evaluation.ragas_runner import run_ragas_evaluation
from app.evaluation.reports import build_report
from app.evaluation.runners import run_baseline, run_crag

router = APIRouter(tags=["evaluation"])


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
