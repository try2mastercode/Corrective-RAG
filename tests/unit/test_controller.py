import json

from app.core.config import Settings
from app.core.models import RetrievedChunk
from app.correction.controller import run_corrective_retrieval
from app.correction.query_rewriter import QUERY_REWRITER_SYSTEM_PROMPT_V1
from app.llm.base import LLMClient
from app.retrieval.grader import RETRIEVAL_GRADER_SYSTEM_PROMPT_V1


def _chunk(chunk_id: str, text: str, score: float = 0.8) -> RetrievedChunk:
    return RetrievedChunk(chunk_id=chunk_id, text=text, score=score, source="doc.txt", metadata={})


class FakeRetriever:
    def __init__(self, results_by_query: dict[str, list[RetrievedChunk]]):
        self._results_by_query = results_by_query
        self.queries_seen: list[str] = []

    def retrieve(self, query: str, top_k: int) -> list[RetrievedChunk]:
        self.queries_seen.append(query)
        return self._results_by_query.get(query, [])


class ScriptedLLM(LLMClient):
    """Routes calls to a grading response table (keyed by passage text) or a
    rewrite response table (keyed by original question), based on the system prompt."""

    def __init__(self, grades: dict[str, dict], rewrites: dict[str, dict]):
        self._grades = grades
        self._rewrites = rewrites
        self.grade_calls = 0
        self.rewrite_calls = 0

    def generate(self, prompt: str, system: str | None = None, temperature: float = 0.0) -> str:
        if system == RETRIEVAL_GRADER_SYSTEM_PROMPT_V1:
            self.grade_calls += 1
            passage = prompt.split("Retrieved passage:\n", 1)[1].rsplit("\n\nReturn JSON only.", 1)[0]
            return json.dumps(self._grades[passage])
        if system == QUERY_REWRITER_SYSTEM_PROMPT_V1:
            self.rewrite_calls += 1
            question = prompt.split("Original question:\n", 1)[1].rsplit("\n\nReturn JSON only.", 1)[0]
            return json.dumps(self._rewrites[question])
        raise AssertionError(f"unexpected system prompt: {system!r}")


def _settings(**overrides) -> Settings:
    defaults = dict(max_retrieval_rounds=2, top_k=8, grader_max_retries=1)
    defaults.update(overrides)
    return Settings(**defaults)


def test_strong_first_retrieval_skips_correction():
    chunk_a = _chunk("a", "highly relevant passage")
    retriever = FakeRetriever({"what is X?": [chunk_a]})
    llm = ScriptedLLM(
        grades={"highly relevant passage": {"score": 0.95, "label": "RELEVANT", "reason": "direct match"}},
        rewrites={},
    )

    result = run_corrective_retrieval("what is X?", retriever, llm, _settings())

    assert len(result.rounds) == 1
    assert result.final_quality.decision == "HIGH"
    assert result.rewrites == []
    assert llm.rewrite_calls == 0
    assert [c.chunk_id for c in result.final_chunks] == ["a"]


def test_weak_retrieval_triggers_rewrite_and_improves():
    chunk_weak = _chunk("weak1", "vaguely related passage")
    chunk_strong = _chunk("strong1", "the exact answer passage")

    retriever = FakeRetriever(
        {
            "vague question": [chunk_weak],
            "specific rewritten question": [chunk_strong],
        }
    )
    llm = ScriptedLLM(
        grades={
            "vaguely related passage": {"score": 0.3, "label": "PARTIALLY_RELEVANT", "reason": "tangential"},
            "the exact answer passage": {"score": 0.95, "label": "RELEVANT", "reason": "direct match"},
        },
        rewrites={"vague question": {"rewritten_query": "specific rewritten question", "reason": "added detail"}},
    )

    result = run_corrective_retrieval("vague question", retriever, llm, _settings())

    # Round 1 (its own retrieval) is weak, which triggers a rewrite. Round 2's own retrieval
    # is strong on its own, so the loop stops there. The *final* evidence set merges both
    # rounds, so its overall quality reflects the earlier weak chunk dragging the mean down --
    # that's the intended "merge, don't discard" behavior, distinct from the per-round decision.
    assert len(result.rounds) == 2
    assert result.rounds[0].quality.decision == "LOW"
    assert result.rounds[1].quality.decision == "HIGH"
    assert len(result.rewrites) == 1
    assert retriever.queries_seen == ["vague question", "specific rewritten question"]
    final_ids = {c.chunk_id for c in result.final_chunks}
    assert "strong1" in final_ids
    # Highest-graded chunk should be ranked first.
    assert result.final_chunks[0].chunk_id == "strong1"


def test_correction_stops_at_max_rounds_when_still_weak():
    chunk_weak = _chunk("weak1", "irrelevant passage one")
    chunk_weak2 = _chunk("weak2", "irrelevant passage two")

    retriever = FakeRetriever({"q1": [chunk_weak], "q2": [chunk_weak2]})
    llm = ScriptedLLM(
        grades={
            "irrelevant passage one": {"score": 0.1, "label": "IRRELEVANT", "reason": "no match"},
            "irrelevant passage two": {"score": 0.15, "label": "IRRELEVANT", "reason": "no match"},
        },
        rewrites={"q1": {"rewritten_query": "q2", "reason": "tried different phrasing"}},
    )

    result = run_corrective_retrieval("q1", retriever, llm, _settings(max_retrieval_rounds=2))

    assert len(result.rounds) == 2
    assert result.final_quality.decision == "LOW"
    assert len(result.rewrites) == 1
    assert result.final_chunks == []  # both graded IRRELEVANT


def test_repeated_rewrite_stops_loop_early():
    chunk_weak = _chunk("weak1", "irrelevant passage")

    retriever = FakeRetriever({"q1": [chunk_weak]})
    llm = ScriptedLLM(
        grades={"irrelevant passage": {"score": 0.1, "label": "IRRELEVANT", "reason": "no match"}},
        rewrites={"q1": {"rewritten_query": "q1", "reason": "no change found"}},
    )

    result = run_corrective_retrieval("q1", retriever, llm, _settings(max_retrieval_rounds=3))

    assert len(result.rounds) == 1
    assert retriever.queries_seen == ["q1"]
    assert len(result.rewrites) == 1


def test_max_rounds_of_one_skips_correction_entirely():
    chunk_weak = _chunk("weak1", "irrelevant passage")
    retriever = FakeRetriever({"q1": [chunk_weak]})
    llm = ScriptedLLM(
        grades={"irrelevant passage": {"score": 0.1, "label": "IRRELEVANT", "reason": "no match"}},
        rewrites={},
    )

    result = run_corrective_retrieval("q1", retriever, llm, _settings(max_retrieval_rounds=1))

    assert len(result.rounds) == 1
    assert result.rewrites == []
    assert llm.rewrite_calls == 0
