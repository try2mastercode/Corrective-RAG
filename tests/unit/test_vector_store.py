from app.core.models import Chunk, ChunkMetadata, utc_now_iso
from app.retrieval.vector_store import ChromaVectorStore


def _chunk(chunk_id: str, document_id: str, text: str) -> Chunk:
    return Chunk(
        text=text,
        metadata=ChunkMetadata(
            document_id=document_id,
            source="doc.txt",
            title="doc",
            page=None,
            chunk_id=chunk_id,
            created_at=utc_now_iso(),
            hash=chunk_id,
        ),
    )


def test_add_and_search(tmp_path):
    store = ChromaVectorStore(str(tmp_path), embedding_dimension=3, embedding_model="fake-model")

    chunks = [_chunk("c1", "d1", "cats are great"), _chunk("c2", "d1", "dogs are great")]
    embeddings = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    store.add_documents(chunks, embeddings)

    results = store.search_with_scores([1.0, 0.0, 0.0], top_k=2)
    assert len(results) == 2
    assert results[0]["chunk_id"] == "c1"
    assert results[0]["score"] > results[1]["score"]


def test_delete_document(tmp_path):
    store = ChromaVectorStore(str(tmp_path), embedding_dimension=3, embedding_model="fake-model")
    chunks = [_chunk("c1", "d1", "text one"), _chunk("c2", "d2", "text two")]
    store.add_documents(chunks, [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])

    deleted = store.delete_document("d1")
    assert deleted == 1

    remaining = store.list_documents()
    assert len(remaining) == 1
    assert remaining[0]["document_id"] == "d2"


def test_search_on_empty_store_returns_empty_list(tmp_path):
    store = ChromaVectorStore(str(tmp_path), embedding_dimension=3, embedding_model="fake-model")
    assert store.search_with_scores([1.0, 0.0, 0.0], top_k=5) == []


def test_embedding_model_mismatch_raises(tmp_path):
    ChromaVectorStore(str(tmp_path), embedding_dimension=3, embedding_model="model-a")

    try:
        ChromaVectorStore(str(tmp_path), embedding_dimension=3, embedding_model="model-b")
        assert False, "expected ValueError for embedding model mismatch"
    except ValueError:
        pass
