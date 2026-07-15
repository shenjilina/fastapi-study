"""Day4 嵌入模型封装。"""

from __future__ import annotations

import math
from functools import lru_cache
from hashlib import sha256
from pathlib import Path

from langchain_core.embeddings import Embeddings

from config.log_config import get_logger
from config.settings import get_settings

logger = get_logger(__name__)


class EmbeddingInitializationError(RuntimeError):
    """嵌入模型初始化失败异常。"""


class HashFallbackEmbeddings(Embeddings):
    """离线环境可用的兜底嵌入实现。

    这个实现不依赖外部模型下载，能够保证向量能力在本地始终可运行。
    """

    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = dimensions

    def _embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        normalized_text = text.strip().lower()
        if not normalized_text:
            return vector

        for token in normalized_text.split():
            digest = sha256(token.encode("utf-8")).digest()
            for index in range(self.dimensions):
                byte_value = digest[index % len(digest)]
                vector[index] += (byte_value / 255.0) - 0.5

        magnitude = math.sqrt(sum(item * item for item in vector))
        if magnitude == 0:
            return vector
        return [item / magnitude for item in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [self._embed_text(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        if not text:
            return [0.0] * self.dimensions
        return self._embed_text(text)


class SentenceTransformerEmbeddings(Embeddings):
    """基于 `sentence-transformers` 的真实嵌入实现。"""

    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - 依赖缺失时走兜底
            raise EmbeddingInitializationError("未安装 sentence-transformers 依赖") from exc

        self.model_name = model_name
        try:
            self.model = SentenceTransformer(model_name, local_files_only=True)
        except Exception as exc:  # pragma: no cover - 运行环境可能离线
            raise EmbeddingInitializationError(
                f"加载嵌入模型失败: {model_name}"
            ) from exc

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()


class ResilientEmbeddingClient(Embeddings):
    """带自动回退能力的嵌入客户端。"""

    def __init__(self) -> None:
        settings = get_settings()
        self.model_name = settings.embedding_model_name
        self.backend_name = "hash_fallback"
        self._backend: Embeddings = HashFallbackEmbeddings()

        # Day4 默认使用本地可运行方案；当配置指向本地模型目录时再启用真实模型。
        if not Path(self.model_name).exists():
            logger.info(
                "Embedding model path not found locally, using fallback backend. model=%s",
                self.model_name,
            )
            return

        try:
            self._backend = SentenceTransformerEmbeddings(self.model_name)
            self.backend_name = "sentence_transformers"
            logger.info("Embedding backend initialized with model: %s", self.model_name)
        except EmbeddingInitializationError as exc:
            logger.warning(
                "Embedding backend fallback activated. reason=%s, fallback=%s",
                exc,
                self.backend_name,
            )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._backend.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._backend.embed_query(text)

    def get_backend_summary(self) -> dict[str, str]:
        """返回当前嵌入后端信息，便于调试。"""
        return {
            "backend": self.backend_name,
            "model_name": self.model_name,
        }


@lru_cache
def get_embedding_client() -> ResilientEmbeddingClient:
    """返回全局唯一的嵌入客户端实例。"""
    return ResilientEmbeddingClient()
