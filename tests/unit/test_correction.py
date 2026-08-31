from app.core.models import Evidence
from app.llm.base import LLMClient
from app.verification.correction import correct_answer


class FakeLLM(LLMClient):
    def __init__(self, response: str):
        self._response = response
        self.last_prompt = None
        self.last_system = None

    def generate(self, prompt: str, system: str | None = None, temperature: float = 0.0) -> str:
        self.last_prompt = prompt
        self.last_system = system
        return self._response


def _evidence() -> Evidence:
    return Evidence(id="E1", type="LOCAL_DOCUMENT", source="doc.txt", location=None, page=None, text="fact")


def test_correct_answer_returns_stripped_llm_output():
    llm = FakeLLM("  The corrected answer.  ")
    result = correct_answer("q", [_evidence()], "draft", ["bad claim"], llm)
    assert result == "The corrected answer."


def test_correct_answer_falls_back_to_draft_if_llm_returns_empty():
    llm = FakeLLM("   ")
    result = correct_answer("q", [_evidence()], "original draft", ["bad claim"], llm)
    assert result == "original draft"


def test_correct_answer_prompt_includes_unsupported_claims_and_evidence():
    llm = FakeLLM("corrected")
    correct_answer("What happened?", [_evidence()], "draft answer text", ["bad claim one"], llm)
    assert "draft answer text" in llm.last_prompt
    assert "bad claim one" in llm.last_prompt
    assert "[E1] fact" in llm.last_prompt
    assert "UNTRUSTED DATA" in llm.last_system
