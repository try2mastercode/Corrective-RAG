import json

from app.core.config import Settings
from app.core.models import CorrectiveRetrievalResult, RetrievalQualityResult, RetrievedChunk, WebSearchResult
from app.correction.controller import apply_web_fallback, run_corrective_retrieval
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


def _weak_correction(chunks=None) -> CorrectiveRetrievalResult:
    return CorrectiveRetrievalResult(
        final_chunks=chunks or [],
        rounds=[],
        rewrites=[],
        final_quality=RetrievalQualityResult(
            mean_score=0.1, best_score=0.1, relevant_ratio=0.0, quality_score=0.1, decision="LOW"
        ),
    )


def _high_correction() -> CorrectiveRetrievalResult:
    return CorrectiveRetrievalResult(
        final_chunks=[_chunk("local1", "great local match", score=0.9)],
        rounds=[],
        rewrites=[],
        final_quality=RetrievalQualityResult(
            mean_score=0.9, best_score=0.9, relevant_ratio=1.0, quality_score=0.9, decision="HIGH"
        ),
    )


class GradingOnlyLLM(LLMClient):
    def __init__(self, grades: dict[str, dict]):
        self._grades = grades
        self.calls = 0

    def generate(self, prompt: str, system: str | None = None, temperature: float = 0.0) -> str:
        assert system == RETRIEVAL_GRADER_SYSTEM_PROMPT_V1
        self.calls += 1
        passage = prompt.split("Retrieved passage:\n", 1)[1].rsplit("\n\nReturn JSON only.", 1)[0]
        return json.dumps(self._grades[passage])


def test_web_fallback_skipped_when_disabled(monkeypatch):
    def _fail_if_called(*args, **kwargs):
        raise AssertionError("web_search should not be called when disabled")

    monkeypatch.setattr("app.correction.controller.web_search", _fail_if_called)

    correction = _weak_correction()
    result = apply_web_fallback("q", correction, GradingOnlyLLM({}), _settings(web_search_enabled=False))

    assert result is correction
    assert result.web_search_triggered is False


def test_web_fallback_skipped_when_local_quality_is_high(monkeypatch):
    def _fail_if_called(*args, **kwargs):
        raise AssertionError("web_search should not be called when local quality is already HIGH")

    monkeypatch.setattr("app.correction.controller.web_search", _fail_if_called)

    correction = _high_correction()
    result = apply_web_fallback("q", correction, GradingOnlyLLM({}), _settings(web_search_enabled=True))

    assert result is correction


def test_web_fallback_merges_relevant_results(monkeypatch):
    web_results = [
        WebSearchResult(url="https://a.example.com", title="A", snippet="a relevant snippet", retrieved_at="t"),
        WebSearchResult(url="https://b.example.com", title="B", snippet="an irrelevant snippet", retrieved_at="t"),
    ]
    monkeypatch.setattr("app.correction.controller.web_search", lambda *a, **kw: web_results)

    llm = GradingOnlyLLM(
        {
            "A\na relevant snippet": {"score": 0.9, "label": "RELEVANT", "reason": "matches"},
            "B\nan irrelevant snippet": {"score": 0.1, "label": "IRRELEVANT", "reason": "no match"},
        }
    )

    correction = _weak_correction()
    result = apply_web_fallback("q", correction, llm, _settings(web_search_enabled=True))

    assert result.web_search_triggered is True
    assert result.web_used is True
    assert len(result.final_chunks) == 1
    assert result.final_chunks[0].source == "https://a.example.com"
    assert result.final_chunks[0].source_type == "WEB_SOURCE"
    assert len(result.web_results) == 2  # raw results preserved for debug transparency


def test_web_fallback_no_results_found(monkeypatch):
    monkeypatch.setattr("app.correction.controller.web_search", lambda *a, **kw: [])

    correction = _weak_correction()
    result = apply_web_fallback("q", correction, GradingOnlyLLM({}), _settings(web_search_enabled=True))

    assert result.web_search_triggered is True
    assert result.web_used is False
    assert result.final_chunks == []


def test_web_fallback_all_results_irrelevant_does_not_pollute_evidence(monkeypatch):
    web_results = [
        WebSearchResult(url="https://a.example.com", title="A", snippet="off topic", retrieved_at="t"),
    ]
    monkeypatch.setattr("app.correction.controller.web_search", lambda *a, **kw: web_results)
    llm = GradingOnlyLLM({"A\noff topic": {"score": 0.05, "label": "IRRELEVANT", "reason": "unrelated"}})

    correction = _weak_correction()
    result = apply_web_fallback("q", correction, llm, _settings(web_search_enabled=True))

    assert result.web_used is False
    assert result.final_chunks == []


def test_web_fallback_appends_after_existing_local_chunks(monkeypatch):
    local_chunk = _chunk("local1", "somewhat useful local passage", score=0.5)
    web_results = [WebSearchResult(url="https://a.example.com", title="A", snippet="good web info", retrieved_at="t")]
    monkeypatch.setattr("app.correction.controller.web_search", lambda *a, **kw: web_results)
    llm = GradingOnlyLLM({"A\ngood web info": {"score": 0.9, "label": "RELEVANT", "reason": "matches"}})

    correction = _weak_correction(chunks=[local_chunk])
    result = apply_web_fallback("q", correction, llm, _settings(web_search_enabled=True))

    assert [c.chunk_id for c in result.final_chunks] == ["local1", result.final_chunks[1].chunk_id]
    assert result.final_chunks[0].source_type == "LOCAL_DOCUMENT"
    assert result.final_chunks[1].source_type == "WEB_SOURCE"
