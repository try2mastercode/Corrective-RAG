from app.core.config import Settings, get_settings
from app.embeddings.base import EmbeddingProvider
from app.embeddings.local import get_embedding_provider
from app.llm.base import LLMClient
from app.llm.ollama import OllamaClient
from app.retrieval.retriever import Retriever
from app.retrieval.vector_store import ChromaVectorStore, get_vector_store


def build_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    settings = settings or get_settings()
    return get_embedding_provider(settings.embedding_model)


def build_vector_store(settings: Settings | None = None) -> ChromaVectorStore:
    settings = settings or get_settings()
    embeddings = build_embedding_provider(settings)
    return get_vector_store(settings.vector_db_path, embeddings.dimension, embeddings.model_name)


def build_retriever(settings: Settings | None = None) -> Retriever:
    settings = settings or get_settings()
    return Retriever(build_embedding_provider(settings), build_vector_store(settings))


def build_llm_client(settings: Settings | None = None) -> LLMClient:
    settings = settings or get_settings()
    return OllamaClient(settings.llm_base_url, settings.llm_model)
