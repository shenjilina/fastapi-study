"""Day7 标准 RAG 问答链封装（企业级 Prompt + 容错）。

严格遵循架构规范：
- 仅依赖底层能力（retriever / llm / text_utils），不依赖任何业务层代码。
- 全局无状态、唯一实例，由 service 层调用。
- 组装标准化链路：知识库隔离检索 -> 上下文拼接 -> Token 截断 -> LLM 生成。
- 内置无检索结果兜底、LLM 调用异常捕获。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from config.log_config import get_logger
from config.settings import get_settings
from core.constants import DEFAULT_MAX_CONTEXT_TOKENS
from core.langchain.llm import LLMInvocationError, get_llm_client
from core.langchain.retriever import KnowledgeBaseRetriever, RetrieverError, get_retriever
from utils.text_utils import truncate_by_tokens

logger = get_logger(__name__)


# 企业级系统 Prompt：约束模型仅在检索上下文内作答，拒绝臆测与越界回答。
SYSTEM_PROMPT_TEMPLATE = """你是一个专业的知识库问答助手。请严格遵循以下规则：

1. 仅根据下方【检索资料】回答用户问题，禁止编造、臆测信息。
2. 如果【检索资料】不足以回答问题，请明确回复："当前知识库中未找到相关资料，无法回答该问题。"
3. 回答需条理清晰，关键信息可分点说明。
4. 如引用资料中的原文，请保持准确，不擅自增删语义。
5. 不回答与知识库内容无关的问题，礼貌引导用户回归主题。

【检索资料】
{context}
"""

# 无检索结果时的兜底回答（不调用 LLM，直接返回）。
NO_CONTEXT_FALLBACK_ANSWER = "当前知识库中未找到相关资料，无法回答该问题。请尝试上传更多文档或调整提问。"

# LLM 调用异常时的兜底回答（保证接口不 500，便于前端处理）。
LLM_ERROR_FALLBACK_ANSWER = "问答服务暂时不可用，请稍后重试。"


class RAGChainError(RuntimeError):
    """RAG 链执行异常（输入参数错误等业务可感知错误）。"""


@dataclass(slots=True)
class RAGSourceDocument:
    """RAG 检索命中的源文档信息，用于溯源展示。"""

    page_content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_content": self.page_content,
            "metadata": self.metadata,
            "score": self.score,
        }


@dataclass(slots=True)
class RAGAnswer:
    """RAG 问答链输出结果。"""

    question: str
    answer: str
    source_documents: list[RAGSourceDocument]
    success: bool
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "source_documents": [doc.to_dict() for doc in self.source_documents],
            "success": self.success,
            "error": self.error,
        }


class StandardRAGChain:
    """统一 RAG 问答链。

    组装标准化链路：知识库隔离检索 -> 上下文拼接 -> Token 截断 -> LLM 生成。
    所有异常在内部捕获并转换为兜底回答，保证调用方拿到稳定的 RAGAnswer。
    """

    def __init__(
        self,
        retriever: KnowledgeBaseRetriever | None = None,
        llm_client: Any | None = None,
    ) -> None:
        self._retriever = retriever or get_retriever()
        self._llm_client = llm_client or get_llm_client()
        settings = get_settings()
        # 上下文最大 Token 数，防止 LLM 输入超限。
        self.max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS
        # 默认检索 TopK，可通过 ask() 参数覆盖。
        self.default_top_k: int = settings.retrieval_top_k

    def _retrieve(self, query: str, knowledge_base_id: int | str | None, top_k: int) -> list[Any]:
        """执行知识库隔离检索，异常时返回空列表而非抛出。"""
        try:
            return self._retriever.search(
                query=query,
                knowledge_base_id=knowledge_base_id,
                top_k=top_k,
            )
        except RetrieverError as exc:
            logger.warning("RAG retrieval failed: %s", exc)
            return []
        except Exception as exc:  # pragma: no cover - 兜底防御
            logger.exception("Unexpected retrieval error: %s", exc)
            return []

    def _format_context(self, documents: list[Any]) -> str:
        """把检索结果拼接为带序号的上下文文本，并按 Token 截断。"""
        if not documents:
            return ""

        blocks: list[str] = []
        for index, doc in enumerate(documents, start=1):
            content = getattr(doc, "page_content", str(doc))
            blocks.append(f"[{index}] {content}")

        joined = "\n\n".join(blocks)
        # 按 Token 截断，防止上下文溢出 LLM 输入窗口。
        return truncate_by_tokens(joined, self.max_context_tokens)

    def _build_messages(self, query: str, context: str) -> list[Any]:
        """构造 LangChain 消息列表（System + Human）。"""
        system_content = SYSTEM_PROMPT_TEMPLATE.format(context=context or "（无）")
        return [SystemMessage(content=system_content), HumanMessage(content=query)]

    def _generate_answer(self, query: str, context: str) -> tuple[str, str | None]:
        """调用 LLM 生成回答，异常时返回兜底文案。

        Returns:
            (answer, error) 元组：error 为 None 表示正常生成。
        """
        # 无检索结果直接兜底，节省 LLM 调用成本。
        if not context:
            return NO_CONTEXT_FALLBACK_ANSWER, None

        messages = self._build_messages(query, context)
        try:
            answer = self._llm_client.invoke_with_messages(messages)
            if not answer or not answer.strip():
                return NO_CONTEXT_FALLBACK_ANSWER, "empty_llm_response"
            return answer.strip(), None
        except LLMInvocationError as exc:
            logger.error("RAG LLM invocation failed: %s", exc)
            return LLM_ERROR_FALLBACK_ANSWER, str(exc)
        except Exception as exc:  # pragma: no cover - 兜底防御
            logger.exception("Unexpected LLM error: %s", exc)
            return LLM_ERROR_FALLBACK_ANSWER, str(exc)

    def ask(
        self,
        query: str,
        *,
        knowledge_base_id: int | str | None = None,
        top_k: int | None = None,
    ) -> RAGAnswer:
        """执行完整 RAG 问答流程。

        Args:
            query: 用户问题文本。
            knowledge_base_id: 知识库 ID，为 None 时检索全局（不推荐生产使用）。
            top_k: 检索结果数量，为 None 时使用默认配置。

        Returns:
            RAGAnswer 结构化结果，包含回答、源文档、成功标志与错误信息。

        Raises:
            RAGChainError: 查询文本为空时抛出。
        """
        if not query or not query.strip():
            raise RAGChainError("query 不能为空")

        effective_top_k = top_k or self.default_top_k

        # 1. 知识库隔离检索
        documents = self._retrieve(query, knowledge_base_id, effective_top_k)

        # 2. 上下文拼接 + Token 截断
        context = self._format_context(documents)

        # 3. LLM 生成（含兜底）
        answer, error = self._generate_answer(query, context)

        # 4. 整理源文档信息，供溯源展示
        source_documents = [
            RAGSourceDocument(
                page_content=str(getattr(doc, "page_content", doc)),
                metadata=dict(getattr(doc, "metadata", {}) or {}),
                score=getattr(doc, "score", None),
            )
            for doc in documents
        ]

        success = error is None
        logger.info(
            "RAG chain done: query_len=%d kb_id=%s docs=%d success=%s",
            len(query),
            knowledge_base_id,
            len(source_documents),
            success,
        )

        return RAGAnswer(
            question=query,
            answer=answer,
            source_documents=source_documents,
            success=success,
            error=error,
        )

    def health_check(self) -> dict[str, Any]:
        """返回 RAG 链运行状态，便于调试和监控。"""
        return {
            "chain": "StandardRAGChain",
            "max_context_tokens": self.max_context_tokens,
            "default_top_k": self.default_top_k,
            "retriever": self._retriever.health_check(),
            "llm": self._llm_client.health_check(),
        }


@lru_cache
def get_rag_chain() -> StandardRAGChain:
    """返回全局唯一的 StandardRAGChain 实例。"""
    return StandardRAGChain()
