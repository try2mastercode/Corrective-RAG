from pathlib import Path

from app.embeddings.base import EmbeddingProvider
from app.ingestion.chunking import chunk_document
from app.ingestion.loaders import load_document
from app.retrieval.vector_store import ChromaVectorStore


def index_document(
    path: str | Path,
    embedding_provider: EmbeddingProvider,
    vector_store: ChromaVectorStore,
    chunk_size_tokens: int = 600,
    overlap_tokens: int = 100,
) -> dict:
    doc = load_document(path)
    chunks = chunk_document(doc, chunk_size_tokens=chunk_size_tokens, overlap_tokens=overlap_tokens)

    if not chunks:
        return {"document_id": doc.document_id, "source": doc.source, "chunks_indexed": 0}

    embeddings = embedding_provider.embed([c.text for c in chunks])
    vector_store.add_documents(chunks, embeddings)

    return {"document_id": doc.document_id, "source": doc.source, "chunks_indexed": len(chunks)}
