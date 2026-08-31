from app.core.models import Evidence, SourceCitation
from app.generation.prompts import ANSWER_GENERATOR_SYSTEM_PROMPT_V1, build_answer_prompt
from app.llm.base import LLMClient


def generate_answer(question: str, evidence: list[Evidence], llm: LLMClient) -> tuple[str, list[SourceCitation]]:
    if not evidence:
        return (
            "I don't have enough retrieved evidence to answer that question.",
            [],
        )

    prompt = build_answer_prompt(question, evidence)
    answer = llm.generate(prompt, system=ANSWER_GENERATOR_SYSTEM_PROMPT_V1, temperature=0.0)

    sources = [
        SourceCitation(id=e.id, source=e.source, source_type=e.type, page=e.page)
        for e in evidence
    ]
    return answer, sources
