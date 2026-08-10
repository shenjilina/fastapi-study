"""Day5 Ollama LLM 全局单例封装，支持超时与重试机制。"""

from __future__ import annotations

import time
from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from config.log_config import get_logger
from config.settings import get_settings
from core.constants import LLM_RETRY_BACKOFF_BASE

logger = get_logger(__name__)


class LLMInitializationError(RuntimeError):
    """LLM 初始化失败异常。"""


class LLMInvocationError(RuntimeError):
    """LLM 调用失败异常（所有重试均失败后抛出）。"""


class OllamaLLMClient:
    """Ollama 大模型客户端，带超时保护与重试退避。

    遵循架构规范：纯无状态、全局唯一，仅被 service 层调用。
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.ollama_base_url
        self.model_name = settings.ollama_model
        self.timeout = settings.ollama_request_timeout
        self.max_retries = settings.ollama_max_retries
        self.temperature = settings.ollama_temperature
        self._llm: BaseChatModel | None = None
        self._available: bool | None = None

    def _build_llm(self) -> BaseChatModel:
        """创建 ChatOllama 实例，失败时抛出 LLMInitializationError。"""
        try:
            from langchain_ollama import ChatOllama

            return ChatOllama(
                base_url=self.base_url,
                model=self.model_name,
                temperature=self.temperature,
                timeout=self.timeout,
            )
        except Exception as exc:
            raise LLMInitializationError(f"初始化 ChatOllama 失败: {exc}") from exc

    @property
    def llm(self) -> BaseChatModel:
        """惰性加载 LLM 实例，首次访问时创建。"""
        if self._llm is None:
            self._llm = self._build_llm()
        return self._llm

    def _retry_invoke(self, messages: list[Any]) -> str:
        """带指数退避重试的调用核心逻辑。"""
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.llm.invoke(messages)
                content = response.content if hasattr(response, "content") else str(response)
                self._available = True
                return str(content)
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "LLM invoke failed (attempt %d/%d): %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    backoff = LLM_RETRY_BACKOFF_BASE ** attempt
                    time.sleep(backoff)

        self._available = False
        raise LLMInvocationError(
            f"LLM 调用在 {self.max_retries} 次重试后仍失败: {last_exc}"
        ) from last_exc

    def invoke(self, prompt: str) -> str:
        """同步调用 LLM 生成回答。

        Args:
            prompt: 用户提问文本。

        Returns:
            LLM 生成的回答文本。

        Raises:
            LLMInvocationError: 所有重试均失败后抛出。
        """
        if not prompt or not prompt.strip():
            raise LLMInvocationError("prompt 不能为空")

        messages = [HumanMessage(content=prompt)]
        return self._retry_invoke(messages)

    def invoke_with_messages(self, messages: list[Any]) -> str:
        """使用完整的消息列表调用 LLM，支持多轮对话场景。

        Args:
            messages: LangChain 消息对象列表。

        Returns:
            LLM 生成的回答文本。
        """
        if not messages:
            raise LLMInvocationError("messages 不能为空")
        return self._retry_invoke(messages)

    def stream_with_messages(self, messages: list[Any]) -> Iterator[str]:
        """流式调用 LLM，逐块产出回答文本（打字机效果）。

        流式输出无法对已发送内容重试：首块产出前失败按重试退避重试，
        产出中途失败则立即抛出 LLMInvocationError，由调用方兜底。

        Args:
            messages: LangChain 消息对象列表。

        Yields:
            LLM 逐块生成的文本片段。

        Raises:
            LLMInvocationError: messages 为空或重试耗尽/中途失败时抛出。
        """
        if not messages:
            raise LLMInvocationError("messages 不能为空")

        started = False
        for attempt in range(1, self.max_retries + 1):
            try:
                for piece in self.llm.stream(messages):
                    content = getattr(piece, "content", None)
                    if content:
                        started = True
                        yield str(content)
                self._available = True
                return
            except Exception as exc:
                if started:
                    # 已输出部分内容，无法整体重试，交由上层做异常兜底。
                    self._available = False
                    raise LLMInvocationError(f"LLM 流式输出中断: {exc}") from exc
                logger.warning(
                    "LLM stream failed (attempt %d/%d): %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    time.sleep(LLM_RETRY_BACKOFF_BASE ** attempt)

        self._available = False
        raise LLMInvocationError(f"LLM 流式调用在 {self.max_retries} 次重试后仍失败")

    def health_check(self) -> dict[str, object]:
        """检查 Ollama 服务可用性，返回状态信息。"""
        status_info: dict[str, object] = {
            "base_url": self.base_url,
            "model_name": self.model_name,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
        }

        if self._available is not None:
            status_info["available"] = self._available
            return status_info

        # 首次检查：尝试轻量调用
        try:
            from langchain_ollama import ChatOllama

            test_llm = ChatOllama(
                base_url=self.base_url,
                model=self.model_name,
                timeout=min(self.timeout, 10),
            )
            test_llm.invoke([HumanMessage(content="ping")])
            self._available = True
            status_info["available"] = True
        except Exception as exc:
            self._available = False
            status_info["available"] = False
            status_info["error"] = str(exc)
            logger.warning("Ollama health check failed: %s", exc)

        return status_info


@lru_cache
def get_llm_client() -> OllamaLLMClient:
    """返回全局唯一的 OllamaLLMClient 实例。"""
    return OllamaLLMClient()
