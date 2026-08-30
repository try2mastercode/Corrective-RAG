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


class RetrieveResponse(BaseModel):
    query: str
    results: list[RetrievedChunk]


class AskRequest(BaseModel):
    question: str
    web_fallback: bool = False
    debug: bool = False


class SourceCitation(BaseModel):
    id: str
    source: str
    page: int | None = None


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceCitation]
    retrieval_status: str


class DocumentInfo(BaseModel):
    document_id: str
    title: str
    source: str
    chunk_count: int
    indexed_at: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
