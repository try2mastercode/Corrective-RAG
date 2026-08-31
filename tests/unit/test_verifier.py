import json

from app.core.config import Settings
from app.core.models import ClaimVerification, Evidence
from app.llm.base import LLMClient
from app.verification.claims import CLAIM_EXTRACTOR_SYSTEM_PROMPT_V1
from app.verification.correction import ANSWER_CORRECTOR_SYSTEM_PROMPT_V1
from app.verification.verifier import (
    CLAIM_VERIFIER_SYSTEM_PROMPT_V1,
    calculate_grounding_score,
    verify_and_correct_answer,
    verify_claim,
)


class FakeLLM(LLMClient):
    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls = 0

    def generate(self, prompt: str, system: str | None = None, temperature: float = 0.0) -> str:
        response = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return response


def _evidence(id_="E1", text="the bridge opened in 1962") -> Evidence:
    return Evidence(id=id_, type="LOCAL_DOCUMENT", source="doc.txt", location=None, page=None, text=text)


def test_verify_claim_parses_supported_result():
    llm = FakeLLM(['{"supported": true, "confidence": 0.9, "evidence_ids": ["E1"]}'])
    result = verify_claim("The bridge opened in 1962.", [_evidence()], llm)
    assert result.supported is True
    assert result.confidence == 0.9
    assert result.evidence_ids == ["E1"]


def test_verify_claim_clamps_confidence():
    llm = FakeLLM(['{"supported": true, "confidence": 1.5, "evidence_ids": []}'])
    result = verify_claim("claim", [], llm)
    assert result.confidence == 1.0


def test_verify_claim_falls_back_to_unsupported_after_malformed_retries():
    llm = FakeLLM(["garbage", "garbage"])
    result = verify_claim("claim", [], llm, max_retries=1)
    assert result.supported is False
    assert result.confidence == 0.0


def test_calculate_grounding_score_empty_is_trivially_supported():
    assert calculate_grounding_score([]) == 1.0


def test_calculate_grounding_score_averages_supported_confidence():
    verifications = [
        ClaimVerification(claim="a", supported=True, evidence_ids=["E1"], confidence=0.9),
        ClaimVerification(claim="b", supported=False, evidence_ids=[], confidence=0.0),
    ]
    assert calculate_grounding_score(verifications) == 0.45


def _settings(**overrides) -> Settings:
    defaults = dict(answer_grounding_threshold=0.75, max_answer_corrections=1, grader_max_retries=1)
    defaults.update(overrides)
    return Settings(**defaults)


class ScriptedVerificationLLM(LLMClient):
    """Routes calls by system-prompt identity, keyed by the exact input text (answer for
    extraction, claim for verification, draft answer for correction) so a multi-round
    extract -> verify -> correct -> re-verify sequence can be scripted precisely."""

    def __init__(self, extractions: dict[str, dict], verifications: dict[str, dict], corrections: dict[str, str]):
        self._extractions = extractions
        self._verifications = verifications
        self._corrections = corrections
        self.calls: list[str] = []

    def generate(self, prompt: str, system: str | None = None, temperature: float = 0.0) -> str:
        self.calls.append(system)
        if system == CLAIM_EXTRACTOR_SYSTEM_PROMPT_V1:
            answer_text = prompt.split("Answer:\n", 1)[1].rsplit("\n\nReturn JSON only.", 1)[0]
            return json.dumps(self._extractions[answer_text])
        if system == CLAIM_VERIFIER_SYSTEM_PROMPT_V1:
            claim_text = prompt.split("\n\nClaim:\n", 1)[1].rsplit("\n\nReturn JSON only.", 1)[0]
            return json.dumps(self._verifications[claim_text])
        if system == ANSWER_CORRECTOR_SYSTEM_PROMPT_V1:
            draft = prompt.split("Draft answer:\n", 1)[1].split("\n\nUnsupported claims", 1)[0]
            return self._corrections[draft]
        raise AssertionError(f"unexpected system prompt: {system!r}")


def test_fully_supported_answer_needs_no_correction():
    draft = "The bridge opened in 1962."
    llm = ScriptedVerificationLLM(
        extractions={draft: {"claims": ["The bridge opened in 1962."]}},
        verifications={
            "The bridge opened in 1962.": {"supported": True, "confidence": 0.95, "evidence_ids": ["E1"]}
        },
        corrections={},
    )

    outcome = verify_and_correct_answer("q", [_evidence()], draft, llm, _settings())

    assert outcome.final_answer == draft
    assert outcome.corrected is False
    assert outcome.gave_up is False
    assert outcome.verification.status == "SUPPORTED"


def test_answer_with_no_claims_is_trivially_supported():
    draft = "I don't have enough evidence to answer that."
    llm = ScriptedVerificationLLM(extractions={draft: {"claims": []}}, verifications={}, corrections={})

    outcome = verify_and_correct_answer("q", [], draft, llm, _settings())

    assert outcome.final_answer == draft
    assert outcome.verification.status == "SUPPORTED"
    assert outcome.verification.grounding_score == 1.0


def test_adversarial_hallucinated_claim_gets_caught_and_corrected():
    """The draft answer asserts a fact ('painted bright red') that the evidence never mentions --
    a classic hallucination. Verification must catch it, trigger a correction, and the corrected
    answer (with the fabricated claim removed) must then verify as fully supported."""
    draft = "The bridge opened in 1962 and was painted bright red."
    corrected = "The bridge opened in 1962."

    llm = ScriptedVerificationLLM(
        extractions={
            draft: {"claims": ["The bridge opened in 1962.", "The bridge was painted bright red."]},
            corrected: {"claims": ["The bridge opened in 1962."]},
        },
        verifications={
            "The bridge opened in 1962.": {"supported": True, "confidence": 0.95, "evidence_ids": ["E1"]},
            "The bridge was painted bright red.": {"supported": False, "confidence": 0.0, "evidence_ids": []},
        },
        corrections={draft: corrected},
    )

    outcome = verify_and_correct_answer("q", [_evidence()], draft, llm, _settings())

    assert outcome.final_answer == corrected
    assert outcome.corrected is True
    assert outcome.gave_up is False
    assert outcome.verification.status == "SUPPORTED"
    assert outcome.correction_attempts == 1


def test_gives_up_with_uncertainty_prefix_after_exhausting_corrections():
    draft = "The bridge was painted bright red."
    llm = ScriptedVerificationLLM(
        extractions={draft: {"claims": ["The bridge was painted bright red."]}},
        verifications={
            "The bridge was painted bright red.": {"supported": False, "confidence": 0.0, "evidence_ids": []}
        },
        corrections={draft: draft},  # correction can't fix it -- evidence just doesn't support any claim
    )

    outcome = verify_and_correct_answer("q", [_evidence()], draft, llm, _settings(max_answer_corrections=1))

    assert outcome.gave_up is True
    assert outcome.verification.status == "UNSUPPORTED"
    assert "could not fully verify" in outcome.final_answer
    assert draft in outcome.final_answer
    assert outcome.correction_attempts == 1
