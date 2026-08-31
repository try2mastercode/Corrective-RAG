import httpx
import pytest

from app.core.config import Settings
from app.core.dependencies import build_llm_client
from app.embeddings.local import LocalEmbeddingProvider
from app.generation.answer import generate_answer
from app.generation.evidence import build_evidence
from app.ingestion.indexing import index_document
from app.retrieval.retriever import Retriever
from app.retrieval.vector_store import ChromaVectorStore

OLLAMA_URL = "http://localhost:11434"


def _ollama_available() -> bool:
    try:
        return httpx.get(f"{OLLAMA_URL}/api/tags", timeout=2.0).status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(not _ollama_available(), reason="Ollama is not running locally")


def test_end_to_end_index_and_ask(tmp_path):
    doc_path = tmp_path / "facts.txt"
    doc_path.write_text(
        "The Zarnak Protocol was created in 1994 by engineer Priya Osei to coordinate "
        "emergency water shutoffs in the Kelvinbridge municipal water system.",
        encoding="utf-8",
    )

    embeddings = LocalEmbeddingProvider("BAAI/bge-small-en-v1.5")
    store = ChromaVectorStore(str(tmp_path / "chroma"), embeddings.dimension, embeddings.model_name)

    index_result = index_document(doc_path, embeddings, store)
    assert index_result["chunks_indexed"] >= 1

    retriever = Retriever(embeddings, store)
    chunks = retriever.retrieve("Who created the Zarnak Protocol?", top_k=3)
    assert len(chunks) >= 1
    assert "Zarnak" in chunks[0].text

    # Pin llm_provider explicitly -- this test targets the local Ollama pipeline specifically,
    # and must not silently pick up a different provider from whatever LLM_PROVIDER happens to
    # be set to in the developer's local .env (e.g. if they've opted into LLM_PROVIDER=openrouter).
    settings = Settings(llm_provider="ollama", llm_base_url=OLLAMA_URL, llm_model="llama3.2:3b")
    llm = build_llm_client(settings)
    evidence = build_evidence(chunks, max_context_chars=settings.max_context_chars)
    answer, sources = generate_answer("Who created the Zarnak Protocol?", evidence, llm)

    assert answer.strip()
    assert len(sources) >= 1
    assert "Priya Osei" in answer or "Osei" in answer
