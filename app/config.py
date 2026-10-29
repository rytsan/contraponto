from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações globais do Contraponto carregadas a partir do .env ou ambiente."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = Field(default="sqlite:///./data/contraponto.db")
    LLAMA_CPP_BASE_URL: str = Field(default="http://127.0.0.1:8080")
    LLAMA_CPP_MODEL: str = Field(default="Meta-Llama-3.1-8B-Instruct-Q4_K_M")
    LLAMA_CPP_NUM_CTX: int = Field(default=8192, ge=512)
    USE_QDRANT: bool = Field(default=False)
    QDRANT_URL: str = Field(default="http://localhost:6333")
    COLLECT_INTERVAL_MINUTES: int = Field(default=60, ge=1)
    REQUEST_TIMEOUT_SECONDS: int = Field(default=20, ge=1)
    RATE_LIMIT_SECONDS: float = Field(default=2.0, ge=0.0)
    FRONTEND_ORIGIN: str = Field(default="http://localhost:5173")
    EMBEDDING_MODEL: str = Field(default="paraphrase-multilingual-MiniLM-L12-v2")
    EMBEDDING_SIMILARITY_THRESHOLD: float = Field(default=0.82, ge=0.0, le=1.0)
    SOURCES_YAML_PATH: str = Field(default="./data/sources.yaml")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna instância singleton das configurações."""
    return Settings()


settings = get_settings()
