"""Day4 Chroma 向量库封装。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from shutil import move
from uuid import uuid4

from langchain_chroma import Chroma

from config.log_config import get_logger
from config.settings import get_settings
from core.langchain.embedding import get_embedding_client

logger = get_logger(__name__)


class ChromaStoreInitializationError(RuntimeError):
    """Chroma 向量库初始化失败异常。"""


class ChromaStoreOperationError(RuntimeError):
    """Chroma 向量库操作失败异常。"""


@dataclass(slots=True)
class VectorSearchResult:
    """向量检索结果结构。"""

    page_content: str
    metadata: dict
    score: float | None = None


class ChromaStoreManager:
    """持久化 Chroma 向量库管理器。"""

    def __init__(self, collection_name: str = "rag_documents") -> None:
        settings = get_settings()
        self.collection_name = collection_name
        self.persist_directory = Path(settings.chroma_persist_directory).resolve()
        self.embedding_client = get_embedding_client()
        self._store = self._initialize_store()

    def _build_store(self) -> Chroma:
        """创建 Chroma 向量库实例。"""
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        return Chroma(
            collection_name=self.collection_name,
            persist_directory=str(self.persist_directory),
            embedding_function=self.embedding_client,
        )

    def _backup_broken_store(self) -> Path | None:
        """检测到向量目录异常时，先备份旧目录再重建。"""
        if not self.persist_directory.exists():
            return None

        # 同时使用时间戳和随机后缀，避免同一秒内重复调用导致路径冲突。
        backup_path = self.persist_directory.with_name(
            f"{self.persist_directory.name}_broken_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:6]}"
        )
        move(str(self.persist_directory), str(backup_path))
        logger.warning("Broken chroma directory moved to backup path: %s", backup_path)
        return backup_path

    def _initialize_store(self) -> Chroma:
        """初始化向量库，失败时执行自动恢复。"""
        try:
            store = self._build_store()
            # 主动访问底层 collection，尽早暴露异常。
            # _collection 是 langchain_chroma.Chroma 暴露的 ChromaDB collection 对象，
            # 虽然带下划线前缀，但这是 LangChain 官方集成中获取 count 的标准方式。
            _ = store._collection.count()
            logger.info(
                "Chroma store ready. collection=%s persist_directory=%s",
                self.collection_name,
                self.persist_directory,
            )
            return store
        except Exception as exc:
            logger.warning("Chroma store initialization failed, trying recovery: %s", exc)
            try:
                self._backup_broken_store()
                store = self._build_store()
                _ = store._collection.count()
                logger.info("Chroma store recovery completed successfully.")
                return store
            except Exception as recovery_exc:
                raise ChromaStoreInitializationError(
                    f"Chroma store initialization failed: {recovery_exc}"
                ) from recovery_exc

    def add_texts(
        self,
        texts: list[str],
        *,
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        """向向量库写入文本。"""
        if not texts:
            raise ChromaStoreOperationError("texts 不能为空")

        document_ids = ids or [uuid4().hex for _ in texts]
        metadata_list = metadatas or [{} for _ in texts]
        if len(metadata_list) != len(texts):
            raise ChromaStoreOperationError("metadatas 数量必须与 texts 一致")
        if len(document_ids) != len(texts):
            raise ChromaStoreOperationError("ids 数量必须与 texts 一致")

        try:
            self._store.add_texts(texts=texts, metadatas=metadata_list, ids=document_ids)
            return document_ids
        except Exception as exc:
            raise ChromaStoreOperationError(f"写入向量库失败: {exc}") from exc

    def similarity_search(
        self,
        query: str,
        *,
        k: int = 4,
        metadata_filter: dict | None = None,
    ) -> list[VectorSearchResult]:
        """执行相似度检索。"""
        if k <= 0:
            raise ChromaStoreOperationError("k 必须大于 0")
        try:
            documents = self._store.similarity_search(query=query, k=k, filter=metadata_filter)
            return [
                VectorSearchResult(
                    page_content=item.page_content,
                    metadata=item.metadata,
                    score=None,
                )
                for item in documents
            ]
        except Exception as exc:
            raise ChromaStoreOperationError(f"检索向量库失败: {exc}") from exc

    def similarity_search_with_score(
        self,
        query: str,
        *,
        k: int = 4,
        metadata_filter: dict | None = None,
    ) -> list[VectorSearchResult]:
        """执行带分数的相似度检索。

        注意：返回的 score 是距离值，越小表示越相似，不是相似度分数。
        """
        if k <= 0:
            raise ChromaStoreOperationError("k 必须大于 0")
        try:
            documents = self._store.similarity_search_with_score(
                query=query,
                k=k,
                filter=metadata_filter,
            )
            return [
                VectorSearchResult(
                    page_content=document.page_content,
                    metadata=document.metadata,
                    score=score,
                )
                for document, score in documents
            ]
        except Exception as exc:
            raise ChromaStoreOperationError(f"检索向量库分数失败: {exc}") from exc

    def delete_by_ids(self, ids: list[str]) -> None:
        """按向量 ID 删除文档。"""
        if not ids:
            return

        try:
            self._store.delete(ids=ids)
        except Exception as exc:
            raise ChromaStoreOperationError(f"删除向量失败: {exc}") from exc

    def delete_by_metadata(self, metadata_filter: dict) -> int:
        """按 metadata 过滤条件批量删除向量。"""
        try:
            result = self._store.get(where=metadata_filter, include=[])
            ids = result.get("ids", [])
            if ids:
                self._store.delete(ids=ids)
            return len(ids)
        except Exception as exc:
            raise ChromaStoreOperationError(f"按 metadata 删除向量失败: {exc}") from exc

    def clear_collection(self) -> int:
        """清空当前 collection，便于本地测试与垃圾清理。"""
        try:
            result = self._store.get(include=[])
            ids = result.get("ids", [])
            if ids:
                self._store.delete(ids=ids)
            return len(ids)
        except Exception as exc:
            raise ChromaStoreOperationError(f"清空向量集合失败: {exc}") from exc

    def count(self) -> int:
        """返回当前 collection 中的向量数量。"""
        try:
            return int(self._store._collection.count())
        except Exception as exc:
            raise ChromaStoreOperationError(f"统计向量数量失败: {exc}") from exc

    def health_check(self) -> dict[str, object]:
        """返回向量库运行状态，便于调试和验证。"""
        return {
            "collection_name": self.collection_name,
            "persist_directory": str(self.persist_directory),
            "count": self.count(),
            "embedding_backend": self.embedding_client.get_backend_summary(),
        }


@lru_cache
def get_chroma_store() -> ChromaStoreManager:
    """返回全局唯一的 Chroma 管理器实例。"""
    return ChromaStoreManager()
