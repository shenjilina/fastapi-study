"""Qdrant vector store wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from uuid import uuid4

from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models

from config.log_config import get_logger
from config.settings import get_settings
from core.langchain.embedding import get_embedding_client

logger = get_logger(__name__)


class QdrantStoreInitializationError(RuntimeError):
    """Qdrant initialization failed."""


class QdrantStoreOperationError(RuntimeError):
    """Qdrant operation failed."""


@dataclass(slots=True)
class VectorSearchResult:
    page_content: str
    metadata: dict
    score: float | None = None


class QdrantStoreManager:
    """Single-collection Qdrant manager used by document and RAG services."""

    def __init__(
        self,
        collection_name: str | None = None,
        *,
        url: str | None = None,
        api_key: str | None = None,
        client: QdrantClient | None = None,
    ) -> None:
        settings = get_settings()
        self.collection_name = collection_name or settings.qdrant_collection_name
        self.url = url or settings.qdrant_url
        self.api_key = api_key if api_key is not None else settings.qdrant_api_key
        self.embedding_client = get_embedding_client()
        if client is not None:
            self._client = client
        elif self.url == ":memory:":
            self._client = QdrantClient(":memory:")
        else:
            self._client = QdrantClient(url=self.url, api_key=self.api_key or None)
        self._ensure_collection()
        self._store = QdrantVectorStore(
            client=self._client,
            collection_name=self.collection_name,
            embedding=self.embedding_client,
        )

    def _ensure_collection(self) -> None:
        try:
            if self._client.collection_exists(self.collection_name):
                return
            dimension = len(self.embedding_client.embed_query("dimension probe"))
            self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
            )
            logger.info("Qdrant collection created: %s", self.collection_name)
        except Exception as exc:
            raise QdrantStoreInitializationError(f"Qdrant initialization failed: {exc}") from exc

    @staticmethod
    def _to_filter(metadata_filter: dict | None) -> models.Filter | None:
        if not metadata_filter:
            return None
        return models.Filter(
            must=[
                models.FieldCondition(
                    key=f"metadata.{key}",
                    match=models.MatchValue(value=value),
                )
                for key, value in metadata_filter.items()
            ]
        )

    def add_texts(
        self,
        texts: list[str],
        *,
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        if not texts:
            raise QdrantStoreOperationError("texts 不能为空")
        document_ids = ids or [uuid4().hex for _ in texts]
        metadata_list = metadatas or [{} for _ in texts]
        if len(metadata_list) != len(texts):
            raise QdrantStoreOperationError("metadatas 数量必须与 texts 一致")
        if len(document_ids) != len(texts):
            raise QdrantStoreOperationError("ids 数量必须与 texts 一致")
        try:
            self._store.add_texts(texts=texts, metadatas=metadata_list, ids=document_ids)
            return document_ids
        except Exception as exc:
            raise QdrantStoreOperationError(f"写入 Qdrant 失败: {exc}") from exc

    def similarity_search(self, query: str, *, k: int = 4, metadata_filter: dict | None = None):
        if k <= 0:
            raise QdrantStoreOperationError("k 必须大于 0")
        try:
            docs = self._store.similarity_search(query, k=k, filter=self._to_filter(metadata_filter))
            return [VectorSearchResult(d.page_content, d.metadata) for d in docs]
        except Exception as exc:
            raise QdrantStoreOperationError(f"检索 Qdrant 失败: {exc}") from exc

    def similarity_search_with_score(
        self, query: str, *, k: int = 4, metadata_filter: dict | None = None
    ):
        if k <= 0:
            raise QdrantStoreOperationError("k 必须大于 0")
        try:
            pairs = self._store.similarity_search_with_score(
                query, k=k, filter=self._to_filter(metadata_filter)
            )
            # Existing RAG threshold expects a distance where lower is better.
            return [VectorSearchResult(d.page_content, d.metadata, 1.0 - score) for d, score in pairs]
        except Exception as exc:
            raise QdrantStoreOperationError(f"检索 Qdrant 分数失败: {exc}") from exc

    def delete_by_ids(self, ids: list[str]) -> None:
        if not ids:
            return
        try:
            self._client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(points=ids),
                wait=True,
            )
        except Exception as exc:
            raise QdrantStoreOperationError(f"删除 Qdrant 向量失败: {exc}") from exc

    def delete_by_metadata(self, metadata_filter: dict) -> int:
        try:
            result = self._client.count(
                collection_name=self.collection_name,
                count_filter=self._to_filter(metadata_filter),
                exact=True,
            )
            self._client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(filter=self._to_filter(metadata_filter)),
                wait=True,
            )
            return int(result.count)
        except Exception as exc:
            raise QdrantStoreOperationError(f"按 metadata 删除 Qdrant 向量失败: {exc}") from exc

    def clear_collection(self) -> int:
        count = self.count()
        if count:
            self._client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(filter=models.Filter(must=[])),
                wait=True,
            )
        return count

    def count(self) -> int:
        try:
            return int(self._client.count(collection_name=self.collection_name, exact=True).count)
        except Exception as exc:
            raise QdrantStoreOperationError(f"统计 Qdrant 向量数量失败: {exc}") from exc

    def health_check(self) -> dict[str, object]:
        return {
            "collection_name": self.collection_name,
            "qdrant_url": self.url,
            "count": self.count(),
            "embedding_backend": self.embedding_client.get_backend_summary(),
        }


@lru_cache
def get_qdrant_store() -> QdrantStoreManager:
    return QdrantStoreManager()
