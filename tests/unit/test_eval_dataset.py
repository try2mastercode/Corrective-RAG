import json

import pytest

from app.evaluation.dataset import load_dataset


def test_load_dataset_parses_valid_entries(tmp_path):
    path = tmp_path / "dataset.json"
    path.write_text(
        json.dumps(
            [
                {"id": "q1", "category": "easy", "question": "Q1?", "ground_truth": "A1"},
                {
                    "id": "q2",
                    "category": "unanswerable",
                    "question": "Q2?",
                    "ground_truth": "n/a",
                    "expected_sources": [],
                },
            ]
        ),
        encoding="utf-8",
    )
    questions = load_dataset(path)
    assert len(questions) == 2
    assert questions[0].id == "q1"
    assert questions[1].category == "unanswerable"


def test_load_dataset_rejects_non_list(tmp_path):
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_dataset(path)


def test_load_dataset_rejects_duplicate_ids(tmp_path):
    path = tmp_path / "dataset.json"
    path.write_text(
        json.dumps(
            [
                {"id": "q1", "category": "easy", "question": "Q1?", "ground_truth": "A1"},
                {"id": "q1", "category": "easy", "question": "Q2?", "ground_truth": "A2"},
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Duplicate"):
        load_dataset(path)


def test_load_dataset_rejects_unknown_category(tmp_path):
    path = tmp_path / "dataset.json"
    path.write_text(
        json.dumps([{"id": "q1", "category": "not_a_real_category", "question": "Q?", "ground_truth": "A"}]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Unknown category"):
        load_dataset(path)


def test_actual_shipped_dataset_loads_and_is_valid():
    questions = load_dataset("data/evaluation/dataset.json")
    assert len(questions) >= 20
    categories = {q.category for q in questions}
    assert categories == {
        "easy",
        "multi_hop",
        "ambiguous",
        "hard_retrieval",
        "unanswerable",
        "distractor",
        "fresh_information",
    }
