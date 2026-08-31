from app.llm.base import LLMClient
from app.verification.claims import extract_claims


class FakeLLM(LLMClient):
    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls = 0

    def generate(self, prompt: str, system: str | None = None, temperature: float = 0.0) -> str:
        response = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return response


def test_extract_claims_parses_valid_json():
    llm = FakeLLM(['{"claims": ["The bridge opened in 1962.", "It spans the Kest River."]}'])
    claims = extract_claims("The bridge opened in 1962 and spans the Kest River.", llm)
    assert claims == ["The bridge opened in 1962.", "It spans the Kest River."]
    assert llm.calls == 1


def test_extract_claims_returns_empty_list_for_no_claims():
    llm = FakeLLM(['{"claims": []}'])
    claims = extract_claims("I don't have enough evidence to answer that.", llm)
    assert claims == []


def test_extract_claims_short_circuits_on_empty_answer():
    llm = FakeLLM(["should not be called"])
    claims = extract_claims("   ", llm)
    assert claims == []
    assert llm.calls == 0


def test_extract_claims_retries_on_malformed_output():
    llm = FakeLLM(["not json", '{"claims": ["a claim"]}'])
    claims = extract_claims("some answer", llm, max_retries=2)
    assert claims == ["a claim"]
    assert llm.calls == 2


def test_extract_claims_falls_back_to_whole_answer_after_exhausting_retries():
    llm = FakeLLM(["garbage", "garbage", "garbage"])
    claims = extract_claims("The answer text.", llm, max_retries=2)
    assert claims == ["The answer text."]
    assert llm.calls == 3


def test_extract_claims_rejects_non_list_claims_field():
    llm = FakeLLM(['{"claims": "not a list"}', '{"claims": ["ok"]}'])
    claims = extract_claims("answer", llm, max_retries=1)
    assert claims == ["ok"]
