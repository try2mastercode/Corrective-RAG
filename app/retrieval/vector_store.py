from functools import lru_cache

import chromadb

from app.core.models import Chunk

COLLECTION_NAME = "documents"


class ChromaVectorStore:
    def __init__(self, persist_path: str, embedding_dimension: int, embedding_model: str):
        self._client = chromadb.PersistentClient(path=persist_path)
        self._embedding_model = embedding_model
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"embedding_model": embedding_model, "dimension": embedding_dimension},
        )
        self._validate_embedding_compatibility(embedding_model)

    def _validate_embedding_compatibility(self, embedding_model: str) -> None:
        stored_model = self._collection.metadata.get("embedding_model") if self._collection.metadata else None
        if stored_model and stored_model != embedding_model:
            raise ValueError(
                f"Vector store was built with embedding model '{stored_model}' but the "
                f"configured model is '{embedding_model}'. Re-index with rebuild_index() "
                "or point VECTOR_DB_PATH to a fresh directory."
            )

    def add_documents(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        if not chunks:
            return
        self._collection.upsert(
            ids=[c.metadata.chunk_id for c in chunks],
            embeddings=embeddings,
            documents=[c.text for c in chunks],
            metadatas=[c.metadata.model_dump() for c in chunks],
        )

    def delete_document(self, document_id: str) -> int:
        existing = self._collection.get(where={"document_id": document_id})
        count = len(existing["ids"])
        if count:
            self._collection.delete(where={"document_id": document_id})
        return count

    def search(self, query_embedding: list[float], top_k: int) -> list[dict]:
        return self.search_with_scores(query_embedding, top_k)

    def search_with_scores(self, query_embedding: list[float], top_k: int) -> list[dict]:
        if self._collection.count() == 0:
            return []
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count()),
        )
        results = []
        for i in range(len(result["ids"][0])):
            distance = result["distances"][0][i]
            # Chroma's default space is squared L2 on normalized vectors; convert to a
            # 0..1-ish similarity score (1 = identical, 0 = dissimilar).
            similarity = max(0.0, 1.0 - distance / 2.0)
            results.append(
                {
                    "chunk_id": result["ids"][0][i],
                    "text": result["documents"][0][i],
                    "score": similarity,
                    "metadata": result["metadatas"][0][i],
                }
            )
        return results

    def list_documents(self) -> list[dict]:
        all_items = self._collection.get()
        documents: dict[str, dict] = {}
        for metadata in all_items["metadatas"]:
            doc_id = metadata["document_id"]
            if doc_id not in documents:
                documents[doc_id] = {
                    "document_id": doc_id,
                    "title": metadata["title"],
                    "source": metadata["source"],
                    "chunk_count": 0,
                    "indexed_at": metadata["created_at"],
                }
            documents[doc_id]["chunk_count"] += 1
        return list(documents.values())

    def rebuild_index(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        self._client.delete_collection(COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"embedding_model": self._embedding_model, "dimension": len(embeddings[0]) if embeddings else 0},
        )
        self.add_documents(chunks, embeddings)


@lru_cache
def get_vector_store(persist_path: str, embedding_dimension: int, embedding_model: str) -> ChromaVectorStore:
    return ChromaVectorStore(persist_path, embedding_dimension, embedding_model)
