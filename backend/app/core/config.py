"""
Central application configuration.

All environment-driven configuration lives here. No other module should
read `os.environ` directly - everything flows through this `Settings`
object so behaviour stays consistent and testable.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---- App ----
    APP_NAME: str = "RAG Service"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    API_PREFIX: str = "/api/v1"

    # ---- Database ----
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://raguser:ragpassword@postgres:5432/ragdb"
    )
    DATABASE_URL_SYNC: str = Field(
        default="postgresql+psycopg2://raguser:ragpassword@postgres:5432/ragdb"
    )

    # ---- Storage ----
    STORAGE_BACKEND: Literal["local"] = "local"
    STORAGE_PATH: str = "/app/storage/uploads"
    MAX_UPLOAD_SIZE_MB: int = 25
    ALLOWED_EXTENSIONS: str = "pdf,doc,docx,txt"

    # ---- Embeddings ----
    EMBEDDING_PROVIDER: Literal["local", "openai", "ollama"] = "ollama"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BASE_URL: str = "http://ollama:11434"
    EMBEDDING_DIMENSION: int = 768
    EMBEDDING_BATCH_SIZE: int = 32

    # ---- LLM ----
    LLM_PROVIDER: Literal["ollama", "openai", "openai_compatible"] = "ollama"
    LLM_MODEL: str = "llama3.1"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "http://ollama:11434"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 1024
    LLM_TIMEOUT_SECONDS: int = 120

    # ---- Chunking ----
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 150
    MIN_CHUNK_SIZE: int = 50
    MAX_CHUNK_SIZE: int = 2000

    # ---- Retrieval ----
    TOP_K: int = 5
    SIMILARITY_THRESHOLD: float = 0.2
    MAX_CONTEXT_CHARS: int = 6000

    # ---- Reranking ----
    RERANKING_ENABLED: bool = False

    @property
    def allowed_extensions_list(self) -> list[str]:
        return [e.strip().lower().lstrip(".") for e in self.ALLOWED_EXTENSIONS.split(",") if e.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
