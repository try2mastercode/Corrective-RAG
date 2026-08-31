from app.core.models import Evidence
from app.generation.answer import generate_answer
from app.generation.prompts import build_answer_prompt
from app.llm.base import LLMClient


class FakeLLM(LLMClient):
    def __init__(self, response: str):
        self._response = response
        self.last_prompt = None
        self.last_system = None

    def generate(self, prompt: str, system: str | None = None, temperature: float = 0.0) -> str:
        self.last_prompt = prompt
        self.last_system = system
        return self._response


def _evidence(id_="E1", type_="LOCAL_DOCUMENT", source="doc.txt", text="some fact", page=None) -> Evidence:
    return Evidence(id=id_, type=type_, source=source, location=None, page=page, text=text)


def test_build_answer_prompt_labels_local_vs_web_sources():
    evidence = [
        _evidence("E1", "LOCAL_DOCUMENT", "report.pdf", "local fact"),
        _evidence("E2", "WEB_SOURCE", "https://example.com", "web fact"),
    ]
    prompt = build_answer_prompt("What happened?", evidence)
    assert "[E1] (local document: report.pdf) local fact" in prompt
    assert "[E2] (web source: https://example.com) web fact" in prompt


def test_generate_answer_returns_insufficient_message_when_no_evidence():
    llm = FakeLLM("should not be called")
    answer, sources = generate_answer("question", [], llm)
    assert "don't have enough" in answer.lower()
    assert sources == []


def test_generate_answer_builds_sources_from_evidence():
    evidence = [_evidence("E1", "LOCAL_DOCUMENT", "report.pdf", "fact", page=5)]
    llm = FakeLLM("The answer is X [E1].")
    answer, sources = generate_answer("question", evidence, llm)

    assert answer == "The answer is X [E1]."
    assert len(sources) == 1
    assert sources[0].id == "E1"
    assert sources[0].source == "report.pdf"
    assert sources[0].source_type == "LOCAL_DOCUMENT"
    assert sources[0].page == 5


def test_generate_answer_uses_grounded_system_prompt():
    evidence = [_evidence()]
    llm = FakeLLM("answer")
    generate_answer("q", evidence, llm)
    assert "UNTRUSTED DATA" in llm.last_system
