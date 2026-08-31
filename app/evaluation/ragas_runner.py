import logging

from app.core.config import Settings
from app.evaluation.runners import RunRecord

logger = logging.getLogger(__name__)

# Isolated behind this module deliberately (todo.md section 19): RAGAS's metric names, import
# paths, and evaluate() signature have changed across versions (0.1.x used lowercase metric
# instances and a HuggingFace-Dataset-based evaluate(); 0.4.x restructured metrics as classes and
# broke on this project's dependency set entirely -- see PROGRESS.md for the version pinned and
# why). If RAGAS's API shifts again, only this file should need to change.

RAGAS_AVAILABLE = True
try:
    from datasets import Dataset
    from langchain_community.chat_models import ChatOllama
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from ragas import evaluate
    from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness
    from ragas.run_config import RunConfig
except ImportError:
    RAGAS_AVAILABLE = False


def build_ragas_llm(settings: Settings):
    judge_model = settings.ragas_judge_model or settings.llm_model
    return ChatOllama(model=judge_model, base_url=settings.llm_base_url, temperature=0.0)


def build_ragas_embeddings(settings: Settings):
    return HuggingFaceEmbeddings(model_name=settings.embedding_model)


def records_to_ragas_dataset(records: list[RunRecord]) -> "Dataset":
    return Dataset.from_dict(
        {
            "question": [r.question for r in records],
            "answer": [r.answer for r in records],
            # RAGAS requires a non-empty contexts list per row even when our pipeline correctly
            # found no evidence (e.g. unanswerable questions) -- an empty string context lets it
            # score those rows instead of erroring out.
            "contexts": [r.contexts if r.contexts else [""] for r in records],
            "ground_truth": [r.ground_truth for r in records],
        }
    )


def run_ragas_evaluation(
    records: list[RunRecord],
    settings: Settings,
    timeout: int = 600,
) -> dict[str, float]:
    """Compute RAGAS metrics for a set of run records. Never raises -- a RAGAS failure (metric
    incompatibility, judge-model timeout, malformed judge output) degrades to an empty result
    rather than taking down the whole evaluation report."""
    if not RAGAS_AVAILABLE:
        logger.warning("ragas is not installed; skipping RAGAS metrics")
        return {}

    if not records:
        return {}

    try:
        dataset = records_to_ragas_dataset(records)
        llm = build_ragas_llm(settings)
        embeddings = build_ragas_embeddings(settings)
        metrics = [faithfulness, answer_relevancy, context_precision, context_recall]

        # max_workers=1: parallel workers contending for the same CPU-bound local model caused
        # spurious TimeoutErrors in testing (see PROGRESS.md) -- sequential is slower but reliable.
        result = evaluate(
            dataset,
            metrics=metrics,
            llm=llm,
            embeddings=embeddings,
            run_config=RunConfig(timeout=timeout, max_workers=1),
            raise_exceptions=False,
        )
        return dict(result)
    except Exception:
        logger.exception("RAGAS evaluation failed; returning no metrics")
        return {}
