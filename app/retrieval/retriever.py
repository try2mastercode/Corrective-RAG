from app.core.models import RetrievedChunk
from app.embeddings.base import EmbeddingProvider
from app.retrieval.vector_store import ChromaVectorStore


class Retriever:
    def __init__(self, embedding_provider: EmbeddingProvider, vector_store: ChromaVectorStore):
        self._embeddings = embedding_provider
        self._store = vector_store

    def retrieve(self, query: str, top_k: int) -> list[RetrievedChunk]:
        query_embedding = self._embeddings.embed_query(query)
        raw_results = self._store.search_with_scores(query_embedding, top_k)

        results = []
        for r in raw_results:
            results.append(
                RetrievedChunk(
                    chunk_id=r["chunk_id"],
                    text=r["text"],
                    score=r["score"],
                    source=r["metadata"]["source"],
                    metadata=r["metadata"],
                )
            )
        return results
