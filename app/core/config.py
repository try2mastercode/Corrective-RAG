from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    llm_provider: str = "ollama"
    llm_base_url: str = "http://localhost:11434"
    llm_model: str = "llama3.2:3b"

    # Embeddings
    embedding_provider: str = "local"
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    # Vector store
    vector_db: str = "chroma"
    vector_db_path: str = "./data/processed/chroma_db"

    # Web search fallback
    web_search_enabled: bool = False
    web_search_provider: str = ""
    web_search_api_key: str = ""

    # Retrieval / correction tuning
    top_k: int = 8
    relevance_threshold: float = 0.65
    answer_grounding_threshold: float = 0.75
    max_retrieval_rounds: int = 2
    max_answer_corrections: int = 1

    # Retrieval quality scoring (Phase 2)
    quality_weight_mean: float = 0.50
    quality_weight_best: float = 0.30
    quality_weight_relevant_ratio: float = 0.20
    retrieval_quality_high_threshold: float = 0.75
    retrieval_quality_medium_threshold: float = 0.55
    grader_max_retries: int = 2

    # App
    app_env: str = "development"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
