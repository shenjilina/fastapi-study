"""Centralized application settings."""

from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    """Typed settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "FastAPI Study RAG Project"
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    api_v1_prefix: str = "/api/v1"

    database_url: str = "sqlite:///./rag_project.db"
    database_echo: bool = False

    cors_allow_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    log_level: str = "INFO"
    log_file: str = "logs/app.log"

    chroma_persist_directory: str = "./chroma"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_request_timeout: int = 60
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    max_upload_size_mb: int = 10

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: str | list[str]) -> list[str]:
        """Allow comma-separated origins in `.env` for local setup."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
