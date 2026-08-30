from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.embeddings.base import EmbeddingProvider


class LocalEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str):
        self._model_name = model_name
        self._model = SentenceTransformer(model_name)
        self._dimension = self._model.get_embedding_dimension()

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()


@lru_cache
def get_embedding_provider(model_name: str) -> LocalEmbeddingProvider:
    return LocalEmbeddingProvider(model_name)
