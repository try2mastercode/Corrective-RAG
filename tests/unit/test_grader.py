from app.core.models import GradedChunk, RetrievalGrade, RetrievedChunk
from app.llm.base import LLMClient
from app.retrieval.grader import (
    _extract_json,
    _parse_grade,
    calculate_retrieval_quality,
    grade_chunk,
)


class FakeLLM(LLMClient):
    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls = 0

    def generate(self, prompt: str, system: str | None = None, temperature: float = 0.0) -> str:
        response = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return response


def _chunk(chunk_id: str = "c1", text: str = "some text") -> RetrievedChunk:
    return RetrievedChunk(chunk_id=chunk_id, text=text, score=0.9, source="doc.txt", metadata={})


def test_extract_json_finds_embedded_object():
    text = 'Sure, here you go: {"score": 0.8, "label": "RELEVANT", "reason": "ok"} thanks'
    parsed = _extract_json(text)
    assert parsed == {"score": 0.8, "label": "RELEVANT", "reason": "ok"}


def test_extract_json_returns_none_for_no_json():
    assert _extract_json("no json here") is None


def test_extract_json_returns_none_for_broken_json():
    assert _extract_json("{score: 0.8 broken}") is None


def test_parse_grade_valid():
    grade = _parse_grade({"score": 0.6, "label": "partially_relevant", "reason": "some overlap"})
    assert grade == RetrievalGrade(score=0.6, label="PARTIALLY_RELEVANT", reason="some overlap")


def test_parse_grade_clamps_out_of_range_score():
    grade = _parse_grade({"score": 1.5, "label": "RELEVANT", "reason": "x"})
    assert grade.score == 1.0

    grade = _parse_grade({"score": -0.5, "label": "RELEVANT", "reason": "x"})
    assert grade.score == 0.0


def test_parse_grade_rejects_invalid_label():
    assert _parse_grade({"score": 0.5, "label": "MAYBE", "reason": "x"}) is None


def test_parse_grade_rejects_missing_fields():
    assert _parse_grade({"label": "RELEVANT"}) is None


def test_grade_chunk_returns_valid_grade_on_first_try():
    llm = FakeLLM(['{"score": 0.9, "label": "RELEVANT", "reason": "direct match"}'])
    grade = grade_chunk("q", "text", llm)
    assert grade.label == "RELEVANT"
    assert grade.score == 0.9
    assert llm.calls == 1


def test_grade_chunk_retries_on_malformed_then_succeeds():
    llm = FakeLLM(["not json at all", '{"score": 0.4, "label": "IRRELEVANT", "reason": "no overlap"}'])
    grade = grade_chunk("q", "text", llm, max_retries=2)
    assert grade.label == "IRRELEVANT"
    assert llm.calls == 2


def test_grade_chunk_falls_back_after_exhausting_retries():
    llm = FakeLLM(["garbage", "still garbage", "more garbage"])
    grade = grade_chunk("q", "text", llm, max_retries=2)
    assert grade.label == "IRRELEVANT"
    assert grade.score == 0.0
    assert llm.calls == 3


def _graded(label: str, score: float) -> GradedChunk:
    return GradedChunk(chunk=_chunk(), grade=RetrievalGrade(score=score, label=label, reason=""))


def test_quality_calculation_all_relevant_is_high():
    graded = [_graded("RELEVANT", 0.9), _graded("RELEVANT", 0.85)]
    result = calculate_retrieval_quality(graded)
    assert result.decision == "HIGH"
    assert result.relevant_ratio == 1.0


def test_quality_calculation_all_irrelevant_is_low():
    graded = [_graded("IRRELEVANT", 0.1), _graded("IRRELEVANT", 0.05)]
    result = calculate_retrieval_quality(graded)
    assert result.decision == "LOW"
    assert result.relevant_ratio == 0.0


def test_quality_calculation_empty_list_is_low():
    result = calculate_retrieval_quality([])
    assert result.decision == "LOW"
    assert result.quality_score == 0.0


def test_quality_calculation_respects_custom_thresholds():
    graded = [_graded("PARTIALLY_RELEVANT", 0.6)]
    result = calculate_retrieval_quality(graded, high_threshold=0.9, medium_threshold=0.1)
    assert result.decision == "MEDIUM"
