"""Centralized application settings."""

from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

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

    # RAG / 模型相关配置
    chroma_persist_directory: str = "./chroma"
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
    jwt_secret_key: str = "fastapi-study-dev-secret-change-me"
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


@lru_cache
def get_settings() -> Settings:
    # 使用缓存避免在应用运行期间重复解析配置。
    return Settings()
