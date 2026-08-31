import json

import app.evaluation.runners as runners_module
from app.core.config import Settings
from app.core.models import RetrievedChunk
from app.evaluation.dataset import EvalQuestion
from app.generation.prompts import ANSWER_GENERATOR_SYSTEM_PROMPT_V1
from app.llm.base import LLMClient
from app.retrieval.grader import RETRIEVAL_GRADER_SYSTEM_PROMPT_V1
from app.verification.claims import CLAIM_EXTRACTOR_SYSTEM_PROMPT_V1


class FakeRetriever:
    def __init__(self, chunks):
        self._chunks = chunks

    def retrieve(self, query, top_k):
        return self._chunks


class AutoPassLLM(LLMClient):
    """Grades every chunk RELEVANT/high and extracts zero claims (so verification trivially
    passes) -- exercises run_baseline/run_crag's wiring without needing a real model."""

    def __init__(self, answer: str = "The answer."):
        self._answer = answer

    def generate(self, prompt, system=None, temperature=0.0):
        if system == RETRIEVAL_GRADER_SYSTEM_PROMPT_V1:
            return json.dumps({"score": 0.9, "label": "RELEVANT", "reason": "matches"})
        if system == CLAIM_EXTRACTOR_SYSTEM_PROMPT_V1:
            return json.dumps({"claims": []})
        if system == ANSWER_GENERATOR_SYSTEM_PROMPT_V1:
            return self._answer
        raise AssertionError(f"unexpected system prompt in AutoPassLLM: {system!r}")


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(chunk_id="c1", text="fact about X", score=0.9, source="doc.txt", metadata={})


def _question() -> EvalQuestion:
    return EvalQuestion(id="q1", category="easy", question="What is X?", ground_truth="X")


def test_run_baseline_produces_record(monkeypatch):
    monkeypatch.setattr(runners_module, "build_retriever", lambda settings: FakeRetriever([_chunk()]))
    monkeypatch.setattr(runners_module, "build_llm_client", lambda settings: AutoPassLLM("The answer is X."))

    record = runners_module.run_baseline(_question(), Settings())

    assert record.answer == "The answer is X."
    assert record.contexts == ["fact about X"]
    assert record.latency_seconds >= 0
    assert record.retrieval_status is None
    assert record.grounding_status is None


def test_run_crag_produces_record_with_full_metadata(monkeypatch):
    monkeypatch.setattr(runners_module, "build_retriever", lambda settings: FakeRetriever([_chunk()]))
    monkeypatch.setattr(runners_module, "build_llm_client", lambda settings: AutoPassLLM("The answer is X."))

    record = runners_module.run_crag(_question(), Settings())

    assert record.answer == "The answer is X."
    assert record.retrieval_status == "HIGH"
    assert record.grounding_status == "SUPPORTED"
    assert record.rewrite_used is False
    assert record.web_used is False
    assert record.answer_corrected is False


def test_run_crag_handles_no_evidence_without_generation_or_verification_calls(monkeypatch):
    """With zero retrieved chunks (e.g. an empty vector store), the correction controller still
    attempts a query rewrite (it can't know retrieval is hopeless), but nothing needs grading
    (no chunks to grade), generation short-circuits to a canned message without calling the LLM,
    and verification is skipped entirely since there's no evidence to check."""
    monkeypatch.setattr(runners_module, "build_retriever", lambda settings: FakeRetriever([]))

    from app.correction.query_rewriter import QUERY_REWRITER_SYSTEM_PROMPT_V1

    class RewriteOnlyLLM(LLMClient):
        def generate(self, prompt, system=None, temperature=0.0):
            if system == QUERY_REWRITER_SYSTEM_PROMPT_V1:
                return json.dumps({"rewritten_query": "a different phrasing", "reason": "tried rewording"})
            raise AssertionError(f"unexpected LLM call with system={system!r}")

    monkeypatch.setattr(runners_module, "build_llm_client", lambda settings: RewriteOnlyLLM())

    record = runners_module.run_crag(_question(), Settings())

    assert record.retrieval_status == "NO_RESULTS"
    assert record.grounding_status == "SUPPORTED"
    assert record.contexts == []
    assert record.rewrite_used is True
