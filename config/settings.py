"""Centralized application settings."""

from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET_KEY = "fastapi-study-dev-secret-change-me"

# 启动时优先加载 `.env`，方便本地开发直接读取环境变量。
load_dotenv()


class Settings(BaseSettings):
    """从环境变量中加载并校验应用配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用基础信息
    app_name: str = "FastAPI Study RAG Project"
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    api_prefix: str = "/api"

    # 数据库配置
    database_url: str = "sqlite:///./rag_project.db"
    database_echo: bool = False

    # 允许跨域访问的前端来源
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    # 日志配置
    log_level: str = "INFO"
    log_file: str = "logs/app.log"

    # Optional deployment bootstrap credentials. These are never given defaults.
    init_admin_username: str | None = None
    init_admin_email: str | None = None
    init_admin_password: str | None = None

    # RAG / 模型相关配置
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection_name: str = "rag_documents"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_request_timeout: int = 60
    ollama_max_retries: int = 3
    ollama_temperature: float = 0.7
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"

    # 文件上传与解析配置
    max_upload_size_mb: int = 10
    allowed_file_extensions: list[str] = Field(
        default_factory=lambda: ["txt", "pdf"]
    )

    # 切片与检索参数（Day10 调优：小切片提升命中精度，高重叠保证语义连续）
    chunk_size: int = 400
    chunk_overlap: int = 80
    retrieval_top_k: int = 5
    # 检索距离阈值（L2 距离，越小越相似）：超过阈值的结果视为低相关并过滤，<= 0 表示不过滤。
    retrieval_score_threshold: float = 1.2

    # JWT 鉴权配置（Day12）：生产环境必须通过环境变量覆盖默认密钥。
    jwt_secret_key: str = DEFAULT_JWT_SECRET_KEY
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 120

    # 多轮对话记忆窗口（Day12）：最多携带最近 N 轮历史问答，防止上下文过载。
    conversation_memory_rounds: int = 4

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: str | list[str]) -> list[str]:
        """支持在 `.env` 中使用逗号分隔的跨域来源配置。"""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("app_env")
    @classmethod
    def _validate_app_env(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"development", "testing", "production"}:
            raise ValueError("APP_ENV must be development, testing, or production")
        return normalized

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
        return normalized

    @model_validator(mode="after")
    def _validate_production_security(self) -> "Settings":
        if self.app_env == "production" and self.jwt_secret_key == DEFAULT_JWT_SECRET_KEY:
            raise ValueError("JWT_SECRET_KEY must be changed before production startup")
        return self


@lru_cache
def get_settings() -> Settings:
    # 使用缓存避免在应用运行期间重复解析配置。
    return Settings()
