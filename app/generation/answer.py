from app.core.models import RetrievedChunk, SourceCitation
from app.generation.prompts import ANSWER_GENERATOR_SYSTEM_PROMPT_V1, build_answer_prompt
from app.llm.base import LLMClient


def generate_answer(question: str, chunks: list[RetrievedChunk], llm: LLMClient) -> tuple[str, list[SourceCitation]]:
    if not chunks:
        return (
            "I don't have enough retrieved evidence to answer that question.",
            [],
        )

    evidence = [{"text": c.text, "source": c.source, "source_type": c.source_type} for c in chunks]
    prompt = build_answer_prompt(question, evidence)
    answer = llm.generate(prompt, system=ANSWER_GENERATOR_SYSTEM_PROMPT_V1, temperature=0.0)

    sources = [
        SourceCitation(
            id=str(i + 1),
            source=c.source,
            source_type=c.source_type,
            page=c.metadata.get("page"),
        )
        for i, c in enumerate(chunks)
    ]
    return answer, sources
