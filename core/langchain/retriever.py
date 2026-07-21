"""Day5 向量检索器封装，支持知识库隔离检索。"""

from __future__ import annotations

from functools import lru_cache

from config.log_config import get_logger
from config.settings import get_settings
from core.constants import MAX_RETRIEVAL_TOP_K, MIN_RETRIEVAL_TOP_K
from core.langchain.chroma_store import ChromaStoreManager, VectorSearchResult, get_chroma_store

logger = get_logger(__name__)


class RetrieverError(RuntimeError):
    """检索器操作失败异常。"""


class KnowledgeBaseRetriever:
    """基于 Chroma 的向量检索器，支持知识库隔离。

    通过 metadata 中的 knowledge_base_id 字段实现不同知识库之间的数据隔离，
    确保检索结果仅来自指定知识库的文档。
    """

    def __init__(self, chroma_store: ChromaStoreManager | None = None) -> None:
        self._store = chroma_store or get_chroma_store()
        settings = get_settings()
        self.default_top_k = settings.retrieval_top_k

    def _build_metadata_filter(self, knowledge_base_id: int | str | None) -> dict | None:
        """构建知识库隔离的 metadata 过滤条件。

        保持 knowledge_base_id 的原始类型，与文档入库时写入的 metadata 类型一致，
        避免 Chroma where 过滤因类型不匹配（int vs str）导致检索结果为空。
        """
        if knowledge_base_id is None:
            return None
        return {"knowledge_base_id": knowledge_base_id}

    def _validate_top_k(self, top_k: int) -> int:
        """校验 top_k 参数范围。"""
        if top_k < MIN_RETRIEVAL_TOP_K:
            raise RetrieverError(f"top_k 不能小于 {MIN_RETRIEVAL_TOP_K}")
        if top_k > MAX_RETRIEVAL_TOP_K:
            logger.warning("top_k=%d exceeds max %d, clamped to max", top_k, MAX_RETRIEVAL_TOP_K)
            return MAX_RETRIEVAL_TOP_K
        return top_k

    def search(
        self,
        query: str,
        *,
        knowledge_base_id: int | str | None = None,
        top_k: int | None = None,
    ) -> list[VectorSearchResult]:
        """在指定知识库内执行相似度检索。

        Args:
            query: 用户查询文本。
            knowledge_base_id: 知识库 ID，为 None 时检索全局。
            top_k: 返回结果数量，默认使用配置值。

        Returns:
            匹配的向量检索结果列表。
        """
        if not query or not query.strip():
            raise RetrieverError("查询文本不能为空")

        effective_top_k = self._validate_top_k(top_k or self.default_top_k)
        metadata_filter = self._build_metadata_filter(knowledge_base_id)

        logger.info(
            "Retrieving documents: query_len=%d kb_id=%s top_k=%d",
            len(query),
            knowledge_base_id,
            effective_top_k,
        )

        return self._store.similarity_search(
            query=query,
            k=effective_top_k,
            metadata_filter=metadata_filter,
        )

    def search_with_score(
        self,
        query: str,
        *,
        knowledge_base_id: int | str | None = None,
        top_k: int | None = None,
    ) -> list[VectorSearchResult]:
        """在指定知识库内执行带分数的相似度检索。

        Returns:
            匹配的向量检索结果列表，包含相似度分数。
        """
        if not query or not query.strip():
            raise RetrieverError("查询文本不能为空")

        effective_top_k = self._validate_top_k(top_k or self.default_top_k)
        metadata_filter = self._build_metadata_filter(knowledge_base_id)

        return self._store.similarity_search_with_score(
            query=query,
            k=effective_top_k,
            metadata_filter=metadata_filter,
        )

    def search_multi_knowledge_base(
        self,
        query: str,
        knowledge_base_ids: list[int | str],
        *,
        top_k: int | None = None,
    ) -> list[VectorSearchResult]:
        """跨多个知识库检索（每个知识库独立检索后合并）。

        Args:
            query: 用户查询文本。
            knowledge_base_ids: 知识库 ID 列表。
            top_k: 每个知识库返回的结果数量。

        Returns:
            合并后的检索结果列表。
        """
        if not knowledge_base_ids:
            raise RetrieverError("knowledge_base_ids 不能为空")

        all_results: list[VectorSearchResult] = []
        for kb_id in knowledge_base_ids:
            results = self.search(query, knowledge_base_id=kb_id, top_k=top_k)
            all_results.extend(results)

        return all_results

    def health_check(self) -> dict[str, object]:
        """返回检索器运行状态。"""
        store_info = self._store.health_check()
        return {
            "retriever": "KnowledgeBaseRetriever",
            "default_top_k": self.default_top_k,
            "store": store_info,
        }


@lru_cache
def get_retriever() -> KnowledgeBaseRetriever:
    """返回全局唯一的检索器实例。"""
    return KnowledgeBaseRetriever()
