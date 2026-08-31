import uuid
from collections import OrderedDict

from pydantic import BaseModel

from app.core.models import utc_now_iso

_MAX_RUNS = 500


class RunTrace(BaseModel):
    run_id: str
    question: str
    created_at: str
    retrieval_rounds: int
    rewritten_queries: list[str]
    web_search_triggered: bool
    web_used: bool
    evidence_ids: list[str]
    generation_latency_seconds: float
    verification_grounding_score: float
    final_status: str


_runs: "OrderedDict[str, RunTrace]" = OrderedDict()


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def record_run(trace: RunTrace) -> None:
    _runs[trace.run_id] = trace
    if len(_runs) > _MAX_RUNS:
        _runs.popitem(last=False)


def get_run(run_id: str) -> RunTrace | None:
    return _runs.get(run_id)


def all_runs() -> list[RunTrace]:
    return list(_runs.values())


def _build_run_trace(
    run_id: str,
    question: str,
    correction,
    evidence,
    verification_outcome,
    latency_seconds: float,
    final_status: str,
) -> RunTrace:
    return RunTrace(
        run_id=run_id,
        question=question,
        created_at=utc_now_iso(),
        retrieval_rounds=len(correction.rounds),
        rewritten_queries=[r.rewritten_query for r in correction.rewrites],
        web_search_triggered=correction.web_search_triggered,
        web_used=correction.web_used,
        evidence_ids=[e.id for e in evidence],
        generation_latency_seconds=latency_seconds,
        verification_grounding_score=verification_outcome.verification.grounding_score,
        final_status=final_status,
    )
