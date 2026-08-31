import json
from pathlib import Path

from pydantic import BaseModel

VALID_CATEGORIES = {
    "easy",
    "multi_hop",
    "ambiguous",
    "hard_retrieval",
    "unanswerable",
    "distractor",
    "fresh_information",
}


class EvalQuestion(BaseModel):
    id: str
    category: str
    question: str
    ground_truth: str
    expected_sources: list[str] = []


def load_dataset(path: str | Path) -> list[EvalQuestion]:
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(raw, list):
        raise ValueError(f"Evaluation dataset must be a JSON list, got {type(raw).__name__}")

    questions = [EvalQuestion(**item) for item in raw]

    seen_ids = set()
    for q in questions:
        if q.id in seen_ids:
            raise ValueError(f"Duplicate question id in dataset: {q.id}")
        seen_ids.add(q.id)
        if q.category not in VALID_CATEGORIES:
            raise ValueError(f"Unknown category {q.category!r} for question {q.id} (valid: {VALID_CATEGORIES})")

    return questions
