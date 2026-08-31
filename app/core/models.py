from datetime import datetime, timezone

from pydantic import BaseModel, Field


class ChunkMetadata(BaseModel):
    document_id: str
    source: str
    title: str
    page: int | None = None
    chunk_id: str
    created_at: str
    hash: str


class Chunk(BaseModel):
    text: str
    metadata: ChunkMetadata


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    score: float
    source: str
    metadata: dict
    source_type: str = "LOCAL_DOCUMENT"  # LOCAL_DOCUMENT | WEB_SOURCE


class RetrieveResponse(BaseModel):
    query: str
    results: list[RetrievedChunk]


class RetrievalGrade(BaseModel):
    score: float
    label: str  # RELEVANT | PARTIALLY_RELEVANT | IRRELEVANT
    reason: str


class GradedChunk(BaseModel):
    chunk: RetrievedChunk
    grade: RetrievalGrade


class RetrievalQualityResult(BaseModel):
    mean_score: float
    best_score: float
    relevant_ratio: float
    quality_score: float
    decision: str  # HIGH | MEDIUM | LOW


class QueryRewrite(BaseModel):
    original_query: str
    rewritten_query: str
    reason: str


class RetrievalRound(BaseModel):
    round: int
    query: str
    quality: RetrievalQualityResult


class Evidence(BaseModel):
    id: str  # "E1", "E2", ...
    type: str  # LOCAL_DOCUMENT | WEB_SOURCE
    source: str
    location: str | None = None
    page: int | None = None
    text: str


class WebSearchResult(BaseModel):
    url: str
    title: str
    snippet: str
    retrieved_at: str


class CorrectiveRetrievalResult(BaseModel):
    final_chunks: list[RetrievedChunk]
    rounds: list[RetrievalRound]
    rewrites: list[QueryRewrite]
    final_quality: RetrievalQualityResult
    web_search_triggered: bool = False
    web_used: bool = False
    web_results: list[WebSearchResult] = Field(default_factory=list)


class ClaimVerification(BaseModel):
    claim: str
    supported: bool
    evidence_ids: list[str]
    confidence: float


class VerificationResult(BaseModel):
    claims: list[ClaimVerification]
    grounding_score: float
    status: str  # SUPPORTED | UNSUPPORTED


class VerificationOutcome(BaseModel):
    final_answer: str
    verification: VerificationResult
    corrected: bool
    correction_attempts: int
    gave_up: bool = False


class AskRequest(BaseModel):
    question: str
    web_fallback: bool = False
    debug: bool = False


class SourceCitation(BaseModel):
    id: str
    source: str
    source_type: str = "LOCAL_DOCUMENT"
    page: int | None = None


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceCitation]
    retrieval_status: str
    grounding_status: str
    debug: dict | None = None


class DocumentInfo(BaseModel):
    document_id: str
    title: str
    source: str
    chunk_count: int
    indexed_at: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
