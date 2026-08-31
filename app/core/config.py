from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    llm_provider: str = "ollama"  # "ollama" (local, default) or "openrouter" (cloud, opt-in)
    llm_base_url: str = "http://localhost:11434"
    llm_model: str = "llama3.2:3b"

    # OpenRouter (only used when llm_provider="openrouter" -- see README for setup)
    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.1-8b-instruct:free"

    # Embeddings
    embedding_provider: str = "local"
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    # Vector store
    vector_db: str = "chroma"
    vector_db_path: str = "./data/processed/chroma_db"

    # Web search fallback
    web_search_enabled: bool = False
    web_search_provider: str = "duckduckgo"
    web_search_api_key: str = ""
    web_search_max_results: int = 5
    web_search_timeout: float = 10.0

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

    # Evidence builder (Phase 5)
    max_context_chars: int = 8000

    # RAGAS evaluation (Phase 7)
    ragas_judge_model: str = ""  # empty = use llm_model as the RAGAS judge too

    # App
    app_env: str = "development"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
