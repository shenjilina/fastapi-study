"""Day7 RAG 问答链自检脚本。

验证链路：
1. 创建用户 -> 创建知识库 -> 上传 TXT 文档（准备 RAG 检索数据）
2. RAG 问答接口：提问 -> 验证返回结构（answer / source_documents / conversation_id）
3. 验证对话记录已落库 -> 查询单条 -> 查询知识库列表 -> 查询用户列表
4. 删除对话记录闭环
5. 权限隔离：其他用户提问被 403 拦截
6. 不存在的知识库提问被 404 拦截
7. 空知识库提问：验证无检索结果兜底回答
8. rag_chain 单元能力验证（无 Ollama 时走兜底，链路仍打通）

说明：本脚本不依赖 Ollama 服务可用，LLM 异常时会返回兜底回答，
      success=False 但 conversation_id 仍会落库（FAILED 状态）。
"""

from __future__ import annotations

import io
from uuid import uuid4

from fastapi.testclient import TestClient

from core.db import create_all_tables, load_all_models
from init_app import app

client = TestClient(app)


def _create_user(suffix: str) -> tuple[int, dict]:
    """创建用户并登录，返回 (user_id, 鉴权请求头)。"""
    username = f"day7_user_{suffix}"
    resp = client.post(
        "/api/v1/auth/create_user",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "Password123",
        },
    )
    assert resp.status_code == 201, f"创建用户失败: {resp.json()}"
    user_id = resp.json()["data"]["id"]
    login_resp = client.post(
        "/api/v1/auth/login", json={"username": username, "password": "Password123"}
    )
    assert login_resp.status_code == 200, f"登录失败: {login_resp.json()}"
    token = login_resp.json()["data"]["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def _create_knowledge_base(user_id: int, suffix: str) -> int:
    """创建知识库并返回 kb_id。"""
    resp = client.post(
        "/api/v1/knowledge-bases",
        json={"owner_id": user_id, "name": f"Day7KB-{suffix}", "description": "Day7 测试知识库"},
    )
    assert resp.status_code == 201, f"创建知识库失败: {resp.json()}"
    return resp.json()["data"]["id"]


def _upload_txt(kb_id: int, content: str, filename: str = "day7_test.txt") -> int:
    """上传 TXT 文档并返回 document_id。"""
    files = {"file": (filename, io.BytesIO(content.encode("utf-8")), "text/plain")}
    resp = client.post(f"/api/v1/knowledge-bases/documents/upload/{kb_id}", files=files)
    assert resp.status_code == 201, f"上传文档失败: {resp.json()}"
    return resp.json()["data"]["document"]["id"]


def _ask(user_id: int, kb_id: int, question: str, headers: dict, top_k: int | None = None) -> dict:
    """调用 RAG 问答接口（必选 JWT 鉴权）。"""
    payload = {"user_id": user_id, "knowledge_base_id": kb_id, "question": question}
    if top_k is not None:
        payload["top_k"] = top_k
    resp = client.post("/api/v1/conversations/ask", json=payload, headers=headers)
    assert resp.status_code == 200, f"问答接口失败: {resp.json()}"
    return resp.json()["data"]


def main() -> None:
    """执行 Day7 全链路自检。"""
    load_all_models()
    create_all_tables()

    suffix = uuid4().hex[:8]

    # 1. 准备数据：用户 + 知识库 + 文档
    user_id, headers = _create_user(suffix)
    print(f"USER OK: id={user_id}")

    kb_id = _create_knowledge_base(user_id, suffix)
    print(f"KB OK: id={kb_id}")

    txt_content = (
        "FastAPI 是一个现代、快速的 Python Web 框架，用于构建 API。"
        "它基于标准 Python 类型提示，支持自动文档生成。"
        "Chroma 是一个轻量级的向量数据库，支持本地持久化。"
        "LangChain 是一个用于构建 LLM 应用的框架，提供了检索、问答等能力。"
    )
    document_id = _upload_txt(kb_id, txt_content)
    print(f"DOC OK: id={document_id}")

    # 2. RAG 问答：验证返回结构完整
    answer_data = _ask(user_id, kb_id, "FastAPI 是什么？", headers)
    assert "question" in answer_data
    assert "answer" in answer_data
    assert "source_documents" in answer_data
    assert "success" in answer_data
    assert "conversation_id" in answer_data
    assert answer_data["question"] == "FastAPI 是什么？"
    assert len(answer_data["answer"]) > 0
    # 已上传文档，应能检索到源文档
    assert len(answer_data["source_documents"]) > 0
    # 源文档应包含 document_id 元数据
    has_doc_id = any(
        "document_id" in (doc.get("metadata") or {}) for doc in answer_data["source_documents"]
    )
    assert has_doc_id, "源文档元数据中应包含 document_id"
    # 对话记录应已落库（无论 LLM 成功与否）
    assert answer_data["conversation_id"] is not None
    conversation_id = answer_data["conversation_id"]
    print(
        f"ASK OK: conv_id={conversation_id} docs={len(answer_data['source_documents'])} "
        f"success={answer_data['success']}"
    )

    # 3. 验证对话记录已落库：查询单条
    get_resp = client.post("/api/v1/conversations/get", json={"conversation_id": conversation_id})
    assert get_resp.status_code == 200, f"查询单条问答失败: {get_resp.json()}"
    conv = get_resp.json()["data"]
    assert conv["id"] == conversation_id
    assert conv["question"] == "FastAPI 是什么？"
    assert conv["knowledge_base_id"] == kb_id
    assert conv["user_id"] == user_id
    print(f"GET ONE OK: status={conv['status']}")

    # 4. 查询知识库对话记录列表
    list_kb_resp = client.post("/api/v1/conversations/list", json={"knowledge_base_id": kb_id})
    assert list_kb_resp.status_code == 200
    kb_convs = list_kb_resp.json()["data"]
    assert len(kb_convs) >= 1
    print(f"LIST BY KB OK: count={len(kb_convs)}")

    # 5. 查询用户对话记录列表
    list_user_resp = client.post("/api/v1/conversations/list", json={"user_id": user_id})
    assert list_user_resp.status_code == 200
    user_convs = list_user_resp.json()["data"]
    assert len(user_convs) >= 1
    print(f"LIST BY USER OK: count={len(user_convs)}")

    # 6. 删除对话记录
    del_resp = client.delete(f"/api/v1/conversations/{conversation_id}")
    assert del_resp.status_code == 200, f"删除问答失败: {del_resp.json()}"
    assert del_resp.json()["data"]["deleted"] is True
    print(f"DELETE OK: conv_id={conversation_id}")

    # 7. 验证删除后查不到
    get_resp2 = client.post("/api/v1/conversations/get", json={"conversation_id": conversation_id})
    assert get_resp2.status_code == 404, "删除后应查不到"
    print("VERIFY DELETE OK: 已删除记录查询返回 404")

    # 8. 权限隔离：其他用户对非自己的知识库提问应被 403 拦截
    other_user_id, other_headers = _create_user(suffix + "_other")
    ask_resp = client.post(
        "/api/v1/conversations/ask",
        headers=other_headers,
        json={
            "user_id": other_user_id,
            "knowledge_base_id": kb_id,
            "question": "测试越权提问",
        },
    )
    assert ask_resp.status_code == 403, f"越权提问应被拦截: {ask_resp.json()}"
    print(f"PERMISSION OK: 越权提问被 403 拦截 - {ask_resp.json()['message']}")

    # 9. 不存在的知识库提问应被 404 拦截
    ask_resp2 = client.post(
        "/api/v1/conversations/ask",
        headers=headers,
        json={
            "user_id": user_id,
            "knowledge_base_id": 999999,
            "question": "测试不存在的知识库",
        },
    )
    assert ask_resp2.status_code == 404, f"不存在的知识库应 404: {ask_resp2.json()}"
    print("NOT FOUND OK: 不存在的知识库被 404 拦截")

    # 10. 空知识库提问：验证无检索结果兜底
    empty_kb_id = _create_knowledge_base(user_id, suffix + "_empty")
    empty_answer = _ask(user_id, empty_kb_id, "这个知识库是空的，能回答吗？", headers)
    assert empty_answer["success"] is False or len(empty_answer["source_documents"]) == 0
    assert "未找到相关资料" in empty_answer["answer"] or empty_answer["success"] is False
    print(f"EMPTY KB OK: 空知识库兜底回答 - success={empty_answer['success']}")

    # 11. rag_chain 单元能力验证
    from core.langchain.rag_chain import get_rag_chain

    chain = get_rag_chain()
    health = chain.health_check()
    assert health["chain"] == "StandardRAGChain"
    assert health["max_context_tokens"] > 0
    assert "retriever" in health
    assert "llm" in health
    print(f"CHAIN HEALTH OK: top_k={health['default_top_k']} tokens={health['max_context_tokens']}")

    # 12. 输入参数校验：空问题应被 422 拦截
    ask_resp3 = client.post(
        "/api/v1/conversations/ask",
        headers=headers,
        json={"user_id": user_id, "knowledge_base_id": kb_id, "question": ""},
    )
    assert ask_resp3.status_code == 422, f"空问题应 422: {ask_resp3.json()}"
    print("VALIDATION OK: 空问题被 422 拦截")

    print("\n=== Day7 全部自检通过 ===")


if __name__ == "__main__":
    main()
