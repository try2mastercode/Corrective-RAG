from app.core.models import QueryRewrite
from app.correction.query_rewriter import _parse_rewrite, rewrite_query
from app.llm.base import LLMClient


class FakeLLM(LLMClient):
    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls = 0

    def generate(self, prompt: str, system: str | None = None, temperature: float = 0.0) -> str:
        response = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return response


def test_parse_rewrite_valid():
    rewrite = _parse_rewrite({"rewritten_query": "better query", "reason": "clarified"}, "orig")
    assert rewrite == QueryRewrite(original_query="orig", rewritten_query="better query", reason="clarified")


def test_parse_rewrite_rejects_empty_rewritten_query():
    assert _parse_rewrite({"rewritten_query": "  ", "reason": "x"}, "orig") is None


def test_parse_rewrite_rejects_missing_field():
    assert _parse_rewrite({"reason": "x"}, "orig") is None


def test_rewrite_query_returns_valid_rewrite_on_first_try():
    llm = FakeLLM(['{"rewritten_query": "expanded question about X", "reason": "added specificity"}'])
    rewrite = rewrite_query("question about X", llm)
    assert rewrite.rewritten_query == "expanded question about X"
    assert rewrite.original_query == "question about X"
    assert llm.calls == 1


def test_rewrite_query_retries_on_malformed_output():
    llm = FakeLLM(["not json", '{"rewritten_query": "fixed query", "reason": "ok"}'])
    rewrite = rewrite_query("q", llm, max_retries=2)
    assert rewrite.rewritten_query == "fixed query"
    assert llm.calls == 2


def test_rewrite_query_falls_back_to_original_after_exhausting_retries():
    llm = FakeLLM(["garbage", "garbage", "garbage"])
    rewrite = rewrite_query("original question", llm, max_retries=2)
    assert rewrite.rewritten_query == "original question"
    assert llm.calls == 3
