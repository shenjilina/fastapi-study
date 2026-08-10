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
from typing import Any, Iterator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from config.log_config import get_logger
from config.settings import get_settings
from core.constants import DEFAULT_MAX_CONTEXT_TOKENS
from core.langchain.llm import LLMInvocationError, get_llm_client
from core.langchain.retriever import KnowledgeBaseRetriever, RetrieverError, get_retriever
from utils.text_utils import truncate_by_tokens

logger = get_logger(__name__)


# 企业级系统 Prompt（Day10 升级）：强化引用规范、答案结构与无关问题拒绝能力。
SYSTEM_PROMPT_TEMPLATE = """你是企业知识库专属问答助手。请严格遵循以下规则：

【回答依据】
1. 仅根据下方【检索资料】回答，禁止编造、臆测或使用资料外的知识。
2. 资料不足以回答时，必须回复："当前知识库中未找到相关资料，无法回答该问题。"
3. 与知识库内容无关的问题（闲聊、无关领域提问），礼貌拒绝并引导用户提问知识库相关内容。

【回答格式】
4. 回答分点组织，先给结论，再展开关键信息。
5. 引用资料原文时在句末标注来源序号，如 [1]、[2]，序号对应【检索资料】编号。
6. 引用必须准确，不擅自增删语义；多个资料冲突时如实说明差异。
7. 使用与用户提问相同的语言回答，保持专业、简洁。

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
        # 上下文最大 Token 数，防 LLM 输入超限。
        self.max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS
        # 默认检索 TopK，可通过 ask() 参数覆盖。
        self.default_top_k: int = settings.retrieval_top_k
        # Day10：检索距离阈值，超过阈值的结果视为低相关并过滤（<= 0 不过滤）。
        self.score_threshold: float = settings.retrieval_score_threshold
    
    def _retrieve(self, query: str, knowledge_base_id: int | str | None, top_k: int) -> list[Any]:
        """执行知识库隔离检索，异常时返回空列表而非抛出。
    
        Day10 优化：改用带分数检索，支持距离阈值过滤与近似切片去重。
        """
        try:
            results = self._retriever.search_with_score(
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
    
        return self._filter_low_relevance(self._deduplicate_documents(results))
    
    def _deduplicate_documents(self, documents: list[Any]) -> list[Any]:
        """去除内容重复的检索结果，避免高重叠切片占用上下文预算。
    
        以归一化后的内容前 64 字符作为指纹，保留首次出现（分数更优）的切片。
        """
        seen_fingerprints: list[str] = []
        unique_documents: list[Any] = []
        for doc in documents:
            content = str(getattr(doc, "page_content", doc))
            fingerprint = "".join(content.split())[:64]
            if fingerprint in seen_fingerprints:
                continue
            seen_fingerprints.append(fingerprint)
            unique_documents.append(doc)
    
        removed = len(documents) - len(unique_documents)
        if removed:
            logger.info("Retrieval dedup removed %d duplicate chunks.", removed)
        return unique_documents
    
    def _filter_low_relevance(self, documents: list[Any]) -> list[Any]:
        """按距离阈值过滤低相关检索结果（score 为 L2 距离，越小越相似）。
    
        无分数的结果不参与过滤；阈值 <= 0 时整体不过滤。
        全部被过滤时保留最优一条，避免误杀导致的体验退化。
        """
        if self.score_threshold <= 0 or not documents:
            return documents
    
        kept = [
            doc for doc in documents
            if getattr(doc, "score", None) is None or doc.score <= self.score_threshold
        ]
        if kept:
            if len(kept) < len(documents):
                logger.info(
                    "Score threshold %.2f filtered %d low-relevance chunks.",
                    self.score_threshold,
                    len(documents) - len(kept),
                )
            return kept
    
        # 全部超阈值：保留距离最小的一条，并提示可能存在低质量检索。
        best = min(documents, key=lambda doc: doc.score)
        logger.info(
            "All chunks exceed score threshold %.2f, keep best one (score=%.4f).",
            self.score_threshold,
            best.score,
        )
        return [best]

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

    def _build_messages(
        self,
        query: str,
        context: str,
        chat_history: list[tuple[str, str]] | None = None,
    ) -> list[Any]:
        """构造 LangChain 消息列表（System + 历史多轮 + Human）。

        Day12：chat_history 为 [(历史问题, 历史回答), ...] 正序列表，
        以 Human/AI 消息对形式插入系统提示与当前提问之间，窗口截断由 service 层负责。
        """
        system_content = SYSTEM_PROMPT_TEMPLATE.format(context=context or "（无）")
        messages: list[Any] = [SystemMessage(content=system_content)]
        for history_question, history_answer in chat_history or []:
            if not history_question or not history_answer:
                continue
            messages.append(HumanMessage(content=history_question))
            messages.append(AIMessage(content=history_answer))
        messages.append(HumanMessage(content=query))
        return messages

    def _generate_answer(
        self,
        query: str,
        context: str,
        chat_history: list[tuple[str, str]] | None = None,
    ) -> tuple[str, str | None]:
        """调用 LLM 生成回答，异常时返回兜底文案。

        Returns:
            (answer, error) 元组：error 为 None 表示正常生成。
        """
        # 无检索结果直接兜底，节省 LLM 调用成本。
        if not context:
            return NO_CONTEXT_FALLBACK_ANSWER, None

        messages = self._build_messages(query, context, chat_history)
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
        chat_history: list[tuple[str, str]] | None = None,
    ) -> RAGAnswer:
        """执行完整 RAG 问答流程。

        Args:
            query: 用户问题文本。
            knowledge_base_id: 知识库 ID，为 None 时检索全局（不推荐生产使用）。
            top_k: 检索结果数量，为 None 时使用默认配置。
            chat_history: 历史问答对列表（正序），用于多轮上下文关联问答。

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
        answer, error = self._generate_answer(query, context, chat_history)

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

    def ask_stream(
        self,
        query: str,
        *,
        knowledge_base_id: int | str | None = None,
        top_k: int | None = None,
        chat_history: list[tuple[str, str]] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """流式执行 RAG 问答，逐事件产出结果（Day11 打字机效果）。

        复用非流式链路的检索、去重、阈值过滤、上下文拼接与 Prompt 逻辑，
        Day12 起同样支持 chat_history 多轮上下文。
        事件序列：sources -> chunk* -> done，LLM 异常时追加 error 事件，
        done 始终作为最后一个事件，保证调用方可稳定收尾。

        Args:
            query: 用户问题文本。
            knowledge_base_id: 知识库 ID，为 None 时检索全局（不推荐生产使用）。
            top_k: 检索结果数量，为 None 时使用默认配置。
            chat_history: 历史问答对列表（正序），用于多轮上下文关联问答。

        Yields:
            事件字典：
            - {"type": "sources", "source_documents": [...]} 检索命中源文档
            - {"type": "chunk", "content": "..."} 文本增量
            - {"type": "error", "message": "...", "error": "..."} LLM 异常兜底
            - {"type": "done", "answer": "...", "success": bool, "error": str | None}

        Raises:
            RAGChainError: 查询文本为空时抛出。
        """
        if not query or not query.strip():
            raise RAGChainError("query 不能为空")

        effective_top_k = top_k or self.default_top_k

        # 1. 知识库隔离检索（复用非流式链路的去重与阈值过滤）
        documents = self._retrieve(query, knowledge_base_id, effective_top_k)
        context = self._format_context(documents)

        source_documents = [
            RAGSourceDocument(
                page_content=str(getattr(doc, "page_content", doc)),
                metadata=dict(getattr(doc, "metadata", {}) or {}),
                score=getattr(doc, "score", None),
            )
            for doc in documents
        ]
        yield {"type": "sources", "source_documents": source_documents}

        # 2. 无检索结果：兜底文案也以流式推送，保证前端打字机体验一致。
        if not context:
            yield {"type": "chunk", "content": NO_CONTEXT_FALLBACK_ANSWER}
            yield {
                "type": "done",
                "answer": NO_CONTEXT_FALLBACK_ANSWER,
                "success": True,
                "error": None,
            }
            logger.info("RAG stream done (no context): kb_id=%s", knowledge_base_id)
            return

        # 3. LLM 流式生成
        messages = self._build_messages(query, context, chat_history)
        chunks: list[str] = []
        try:
            for delta in self._llm_client.stream_with_messages(messages):
                chunks.append(delta)
                yield {"type": "chunk", "content": delta}
        except LLMInvocationError as exc:
            logger.error("RAG stream LLM failed: %s", exc)
            partial = "".join(chunks).strip()
            yield {
                "type": "error",
                "message": LLM_ERROR_FALLBACK_ANSWER,
                "error": str(exc),
            }
            yield {
                "type": "done",
                "answer": partial or LLM_ERROR_FALLBACK_ANSWER,
                "success": False,
                "error": str(exc),
            }
            return
        except Exception as exc:  # pragma: no cover - 兜底防御
            logger.exception("Unexpected RAG stream error: %s", exc)
            yield {
                "type": "error",
                "message": LLM_ERROR_FALLBACK_ANSWER,
                "error": str(exc),
            }
            yield {
                "type": "done",
                "answer": "".join(chunks).strip() or LLM_ERROR_FALLBACK_ANSWER,
                "success": False,
                "error": str(exc),
            }
            return

        answer = "".join(chunks).strip()
        if not answer:
            # LLM 返回空内容：以兜底文案收尾，标记失败便于追溯。
            yield {"type": "chunk", "content": NO_CONTEXT_FALLBACK_ANSWER}
            yield {
                "type": "done",
                "answer": NO_CONTEXT_FALLBACK_ANSWER,
                "success": False,
                "error": "empty_llm_response",
            }
            return

        logger.info(
            "RAG stream done: query_len=%d kb_id=%s docs=%d chunks=%d",
            len(query),
            knowledge_base_id,
            len(source_documents),
            len(chunks),
        )
        yield {"type": "done", "answer": answer, "success": True, "error": None}

    def health_check(self) -> dict[str, Any]:
        """返回 RAG 链运行状态，便于调试和监控。"""
        return {
            "chain": "StandardRAGChain",
            "max_context_tokens": self.max_context_tokens,
            "default_top_k": self.default_top_k,
            "score_threshold": self.score_threshold,
            "retriever": self._retriever.health_check(),
            "llm": self._llm_client.health_check(),
        }


@lru_cache
def get_rag_chain() -> StandardRAGChain:
    """返回全局唯一的 StandardRAGChain 实例。"""
    return StandardRAGChain()
