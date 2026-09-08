"""Day12 多轮对话记忆 + 用户权限体系自检脚本。

验证目标：
1. 登录签发 JWT：注册 -> 登录 -> 返回 access_token / token_type / expires_in
2. 登录异常兜底：密码错误 401，统一响应格式
3. /users/me 鉴权端点：有效令牌 200、缺失令牌 401、过期令牌 401
4. 多轮对话记忆连贯：同 session 第二轮提问携带第一轮 Human/AI 历史消息
5. 记忆窗口优化：超过 conversation_memory_rounds 时仅携带最近 N 轮
6. 数据隔离：他人知识库 403、令牌态冒用他人 user_id 403、会话记忆不跨用户泄漏
7. 流式接口令牌态校验：/ask/stream 冒用身份同样 403
8. 向后兼容：无令牌调用既有问答链路不受影响

说明：
- 场景 4-6 使用捕获式打桩 LLM，确定性断言送入 LLM 的消息结构，不依赖 Ollama。
- 打桩前会上传文档保证检索有命中，避免空上下文走兜底不调用 LLM。
"""

from __future__ import annotations

import io
from uuid import uuid4

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage

from config.settings import get_settings
from core.db import create_all_tables, load_all_models
from core.langchain.rag_chain import get_rag_chain
from core.security import create_access_token
from init_app import app

client = TestClient(app)

ASK_URL = "/api/v1/conversations/ask"
STREAM_URL = "/api/v1/conversations/ask/stream"


class _CaptureLLM:
    """捕获式打桩 LLM：记录每次调用的完整消息列表，返回固定回答。"""

    def __init__(self) -> None:
        self.calls: list[list] = []

    def invoke_with_messages(self, messages):
        self.calls.append(list(messages))
        return "打桩回答：已结合上下文生成。"

    def stream_with_messages(self, messages):
        self.calls.append(list(messages))
        yield "打桩回答："
        yield "已结合上下文生成。"

    def health_check(self):
        return {"backend": "capture-fake"}


def _register(username: str, email: str) -> int:
    resp = client.post(
        "/api/v1/users",
        json={"username": username, "email": email, "password": "Password123"},
    )
    assert resp.status_code == 201, f"创建用户失败: {resp.json()}"
    return resp.json()["data"]["id"]


def _login(username: str, password: str = "Password123"):
    return client.post("/api/v1/login", json={"username": username, "password": password})


def _create_kb(user_id: int, name: str) -> int:
    resp = client.post(
        "/api/v1/knowledge-bases",
        json={"owner_id": user_id, "name": name, "description": "Day12 测试知识库"},
    )
    assert resp.status_code == 201, f"创建知识库失败: {resp.json()}"
    return resp.json()["data"]["id"]


def _upload_txt(kb_id: int, content: str, filename: str):
    files = {"file": (filename, io.BytesIO(content.encode("utf-8")), "text/plain")}
    return client.post(f"/api/v1/knowledge-bases/documents/upload/{kb_id}", files=files)


def _history_pairs(messages: list) -> list[tuple[str, str]]:
    """从 LLM 消息列表中提取系统提示之后、当前提问之前的 Human/AI 历史对。"""
    pairs: list[tuple[str, str]] = []
    body = messages[1:-1]  # 去掉 System 与最后一条当前 Human
    for index in range(0, len(body), 2):
        human, ai = body[index], body[index + 1]
        assert isinstance(human, HumanMessage) and isinstance(ai, AIMessage), (
            f"历史消息应为 Human/AI 成对结构: {body}"
        )
        pairs.append((str(human.content), str(ai.content)))
    return pairs


def main() -> None:
    """执行 Day12 多轮记忆与权限体系自检。"""
    load_all_models()
    create_all_tables()

    suffix = uuid4().hex[:8]
    settings = get_settings()
    rag_chain = get_rag_chain()
    original_llm = rag_chain._llm_client
    capture = _CaptureLLM()

    # ================================================================
    # 场景 1：注册 + 登录签发 JWT
    # ================================================================
    user_a_name = f"day12_alice_{suffix}"
    user_a_id = _register(user_a_name, f"{user_a_name}@example.com")
    login_resp = _login(user_a_name)
    assert login_resp.status_code == 200, f"登录应 200: {login_resp.json()}"
    login_data = login_resp.json()["data"]
    assert login_data["user_id"] == user_a_id
    assert login_data["access_token"], "登录应签发 access_token"
    assert login_data["token_type"] == "bearer"
    assert login_data["expires_in"] > 0, "expires_in 应为正数"
    token_a = login_data["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}
    print("[1] LOGIN OK: 登录签发 JWT（access_token/bearer/expires_in）")

    # ================================================================
    # 场景 2：登录异常兜底（密码错误 401 统一格式）
    # ================================================================
    bad_login = _login(user_a_name, password="WrongPassword1")
    assert bad_login.status_code == 401, f"密码错误应 401: {bad_login.status_code}"
    assert bad_login.json()["code"] != 0, "401 应为统一失败格式"
    print("[2] LOGIN FAIL OK: 密码错误 401 + 统一格式")

    # ================================================================
    # 场景 3：/users/me 鉴权端点（有效 / 缺失 / 过期令牌）
    # ================================================================
    me_resp = client.get("/api/v1/users/me", headers=headers_a)
    assert me_resp.status_code == 200, f"/users/me 应 200: {me_resp.status_code}"
    assert me_resp.json()["data"]["id"] == user_a_id

    no_token_resp = client.get("/api/v1/users/me")
    assert no_token_resp.status_code == 401, "缺失令牌应 401"
    assert no_token_resp.json()["code"] != 0

    expired_token = create_access_token(
        user_id=user_a_id, username=user_a_name, expires_minutes=-1
    )
    expired_resp = client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert expired_resp.status_code == 401, "过期令牌应 401"
    assert "过期" in expired_resp.json()["message"]

    tampered_resp = client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {token_a[:-6]}tamper"}
    )
    assert tampered_resp.status_code == 401, "篡改令牌应 401"
    print("[3] /users/me OK: 有效令牌 200，缺失/过期/篡改令牌 401")

    # ================================================================
    # 准备：知识库 + 文档（保证检索有命中，LLM 打桩被调用）
    # ================================================================
    kb_a = _create_kb(user_a_id, f"Day12KB-A-{suffix}")
    txt_content = (
        "FastAPI 是一个现代的 Python Web 框架，支持自动文档生成。"
        "Qdrant 是一个高性能向量数据库，支持相似度检索。"
        "LangChain 提供了检索、问答等 RAG 核心能力的封装。"
    )
    upload_resp = _upload_txt(kb_a, txt_content, f"day12_{suffix}.txt")
    assert upload_resp.status_code == 201, f"上传文档失败: {upload_resp.json()}"

    # ================================================================
    # 场景 4：多轮对话记忆连贯（第二轮携带第一轮 Human/AI 历史）
    # ================================================================
    session_id = f"sess-{suffix}"
    try:
        rag_chain._llm_client = capture
        first = client.post(
            ASK_URL,
            headers=headers_a,
            json={
                "user_id": user_a_id,
                "knowledge_base_id": kb_a,
                "question": "FastAPI 是什么框架？",
                "conversation_session_id": session_id,
            },
        )
        assert first.status_code == 200, f"第一轮提问应 200: {first.json()}"
        first_data = first.json()["data"]
        assert first_data["success"] is True, "打桩 LLM 应成功生成"
        assert len(capture.calls) == 1
        assert _history_pairs(capture.calls[0]) == [], "第一轮不应携带历史"

        second = client.post(
            ASK_URL,
            headers=headers_a,
            json={
                "user_id": user_a_id,
                "knowledge_base_id": kb_a,
                "question": "我上一轮问了什么？",
                "conversation_session_id": session_id,
            },
        )
        assert second.status_code == 200, f"第二轮提问应 200: {second.json()}"
        assert len(capture.calls) == 2
        history = _history_pairs(capture.calls[1])
        assert history == [("FastAPI 是什么框架？", "打桩回答：已结合上下文生成。")], (
            f"第二轮应携带第一轮完整历史: {history}"
        )
        # 当前提问必须是最后一条 Human 消息
        last_message = capture.calls[1][-1]
        assert isinstance(last_message, HumanMessage)
        assert last_message.content == "我上一轮问了什么？"
    finally:
        rag_chain._llm_client = original_llm
    print("[4] MEMORY OK: 第二轮携带第一轮 Human/AI 历史，上下文连贯")

    # ================================================================
    # 场景 5：记忆窗口优化（仅携带最近 N 轮）
    # ================================================================
    original_rounds = settings.conversation_memory_rounds
    capture.calls.clear()
    try:
        settings.conversation_memory_rounds = 2
        rag_chain._llm_client = capture
        for index in range(1, 4):
            resp = client.post(
                ASK_URL,
                headers=headers_a,
                json={
                    "user_id": user_a_id,
                    "knowledge_base_id": kb_a,
                    "question": f"窗口测试第 {index} 问",
                    "conversation_session_id": session_id,
                },
            )
            assert resp.status_code == 200, f"窗口测试第 {index} 问失败: {resp.json()}"

        # 第 4 次调用时前面已有 4 轮（场景4两轮 + 本场景前两轮），窗口=2 只带最近 2 轮
        history = _history_pairs(capture.calls[-1])
        assert len(history) == 2, f"记忆窗口应截断为 2 轮: {len(history)}"
        assert history[-1][0] == "窗口测试第 2 问", f"应保留最新轮次: {history}"
    finally:
        settings.conversation_memory_rounds = original_rounds
        rag_chain._llm_client = original_llm
    print("[5] WINDOW OK: 历史超过窗口时仅携带最近 2 轮，防上下文过载")

    # ================================================================
    # 场景 6：数据隔离（知识库越权 / 身份冒用 / 会话记忆跨用户隔离）
    # ================================================================
    user_b_name = f"day12_bob_{suffix}"
    user_b_id = _register(user_b_name, f"{user_b_name}@example.com")
    token_b = _login(user_b_name).json()["data"]["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 6.1 用户 B 用自己的令牌 + A 的知识库 -> 知识库归属校验 403
    cross_kb = client.post(
        ASK_URL,
        headers=headers_b,
        json={"user_id": user_b_id, "knowledge_base_id": kb_a, "question": "越权提问"},
    )
    assert cross_kb.status_code == 403, f"他人知识库应 403: {cross_kb.status_code}"

    # 6.2 用户 B 令牌 + 请求体冒用 A 的 user_id -> 身份冒用拦截 403
    impersonate = client.post(
        ASK_URL,
        headers=headers_b,
        json={"user_id": user_a_id, "knowledge_base_id": kb_a, "question": "冒用身份提问"},
    )
    assert impersonate.status_code == 403, f"冒用他人身份应 403: {impersonate.status_code}"
    assert "无权" in impersonate.json()["message"]

    # 6.3 会话记忆隔离：B 用同名 session 提问，不得携带 A 的历史
    kb_b = _create_kb(user_b_id, f"Day12KB-B-{suffix}")
    upload_b = _upload_txt(kb_b, txt_content, f"day12_b_{suffix}.txt")
    assert upload_b.status_code == 201, f"B 上传文档失败: {upload_b.json()}"
    capture.calls.clear()
    try:
        rag_chain._llm_client = capture
        resp = client.post(
            ASK_URL,
            headers=headers_b,
            json={
                "user_id": user_b_id,
                "knowledge_base_id": kb_b,
                "question": "B 的独立提问",
                "conversation_session_id": session_id,  # 与 A 相同的会话标识
            },
        )
        assert resp.status_code == 200, f"B 提问应 200: {resp.json()}"
        assert _history_pairs(capture.calls[0]) == [], "B 不得读到 A 的会话记忆"
    finally:
        rag_chain._llm_client = original_llm
    print("[6] ISOLATION OK: 知识库越权/身份冒用 403，会话记忆不跨用户泄漏")

    # ================================================================
    # 场景 7：流式接口令牌态校验（冒用身份同样 403，流前拦截）
    # ================================================================
    stream_impersonate = client.post(
        STREAM_URL,
        headers=headers_b,
        json={"user_id": user_a_id, "knowledge_base_id": kb_a, "question": "流式冒用提问"},
    )
    assert stream_impersonate.status_code == 403, "流式冒用身份应流前 403"

    stream_ok = client.post(
        STREAM_URL,
        headers=headers_a,
        json={
            "user_id": user_a_id,
            "knowledge_base_id": kb_a,
            "question": "流式多轮提问",
            "conversation_session_id": session_id,
        },
    )
    assert stream_ok.status_code == 200, f"令牌态流式应 200: {stream_ok.status_code}"
    assert stream_ok.headers.get("content-type", "").startswith("text/event-stream")
    print("[7] STREAM AUTH OK: 流式接口冒用 403、本人令牌正常出流")

    # ================================================================
    # 场景 8：向后兼容（无令牌调用既有问答链路）
    # ================================================================
    legacy = client.post(
        ASK_URL,
        json={"user_id": user_a_id, "knowledge_base_id": kb_a, "question": "无令牌兼容提问"},
    )
    assert legacy.status_code == 200, f"无令牌调用应兼容 200: {legacy.status_code}"
    assert len(legacy.json()["data"]["answer"]) > 0
    print("[8] COMPAT OK: 无令牌调用兼容旧客户端")

    print("\n=== Day12 全部自检通过 ===")


if __name__ == "__main__":
    main()
