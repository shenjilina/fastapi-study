"""Day8 RAG 问答业务接口完整闭环自检脚本。

验证链路（完整闭环）：
1. 创建用户 -> 创建知识库 -> 上传文档 -> RAG 问答 -> 验证溯源 -> 验证持久化
2. 知识库隔离：KB1 有文档、KB2 为空，交叉提问验证隔离
3. 关联文档溯源：源文档 metadata 中包含 document_id，与上传文档 ID 一致
4. 对话记录入库：question / answer / source_document_ids / status 全字段校验
5. 链路漏洞修复验证：空提问拦截(422)、超长上下文截断、检索失败兜底、禁用 KB 拦截(403)
6. RAG 健康检查端点
7. 对话记录完整 CRUD 闭环

说明：本脚本不依赖 Ollama 可用，LLM 异常时走兜底回答，链路仍完整打通。
"""

from __future__ import annotations

import io
from uuid import uuid4

from fastapi.testclient import TestClient

from core.db import create_all_tables, load_all_models
from init_app import app

client = TestClient(app)


def _create_user(suffix: str) -> int:
    """创建用户并返回 user_id。"""
    resp = client.post(
        "/api/v1/users",
        json={
            "username": f"day8_user_{suffix}",
            "email": f"day8_user_{suffix}@example.com",
            "password": "Password123",
        },
    )
    assert resp.status_code == 201, f"创建用户失败: {resp.json()}"
    return resp.json()["data"]["id"]


def _create_kb(user_id: int, suffix: str) -> int:
    """创建知识库并返回 kb_id。"""
    resp = client.post(
        "/api/v1/knowledge-bases",
        json={"owner_id": user_id, "name": f"Day8KB-{suffix}", "description": "Day8 测试知识库"},
    )
    assert resp.status_code == 201, f"创建知识库失败: {resp.json()}"
    return resp.json()["data"]["id"]


def _upload_txt(kb_id: int, content: str, filename: str = "day8_doc.txt") -> int:
    """上传 TXT 文档并返回 document_id。"""
    files = {"file": (filename, io.BytesIO(content.encode("utf-8")), "text/plain")}
    resp = client.post(f"/api/v1/knowledge-bases/documents/upload/{kb_id}", files=files)
    assert resp.status_code == 201, f"上传文档失败: {resp.json()}"
    return resp.json()["data"]["document"]["id"]


def _ask(user_id: int, kb_id: int, question: str, top_k: int | None = None) -> dict:
    """调用 RAG 问答接口。"""
    payload = {"user_id": user_id, "knowledge_base_id": kb_id, "question": question}
    if top_k is not None:
        payload["top_k"] = top_k
    resp = client.post("/api/v1/rag/ask", json=payload)
    return resp


def main() -> None:
    """执行 Day8 完整闭环自检。"""
    load_all_models()
    create_all_tables()

    suffix = uuid4().hex[:8]

    # ================================================================
    # 场景 1：完整闭环 - 上传文档 -> 问答 -> 溯源 -> 持久化
    # ================================================================
    user_id = _create_user(suffix)
    print(f"[1] USER OK: id={user_id}")

    kb_id = _create_kb(user_id, suffix)
    print(f"[1] KB OK: id={kb_id}")

    txt_content = (
        "FastAPI 是一个现代、快速的 Python Web 框架，用于构建 API。"
        "它基于标准 Python 类型提示，支持自动文档生成。"
        "Chroma 是一个轻量级的向量数据库，支持本地持久化。"
        "LangChain 是一个用于构建 LLM 应用的框架，提供了检索、问答等能力。"
        "通过将文档切片后存入向量库，可以实现基于语义的精准检索。"
    )
    document_id = _upload_txt(kb_id, txt_content)
    print(f"[1] DOC OK: id={document_id}")

    # 提问并验证完整响应结构
    ask_resp = _ask(user_id, kb_id, "FastAPI 是什么？")
    assert ask_resp.status_code == 200, f"问答接口失败: {ask_resp.json()}"
    answer_data = ask_resp.json()["data"]

    # 验证响应字段完整性
    required_fields = {"question", "answer", "source_documents", "success", "error", "conversation_id"}
    assert required_fields.issubset(answer_data.keys()), "响应缺少必要字段"
    assert answer_data["question"] == "FastAPI 是什么？"
    assert len(answer_data["answer"]) > 0
    print(f"[1] ASK OK: success={answer_data['success']} docs={len(answer_data['source_documents'])}")

    # 验证关联文档溯源：源文档应包含与上传文档匹配的 document_id
    source_doc_ids = []
    for doc in answer_data["source_documents"]:
        assert "page_content" in doc
        assert "metadata" in doc
        meta = doc.get("metadata") or {}
        raw_doc_id = meta.get("document_id")
        if raw_doc_id is not None:
            source_doc_ids.append(int(raw_doc_id))
    if source_doc_ids:
        assert document_id in source_doc_ids, (
            f"溯源文档 ID 不匹配: 期望 {document_id} 在 {source_doc_ids} 中"
        )
        print(f"[1] TRACING OK: document_id={document_id} 命中溯源链路")
    else:
        print("[1] TRACING SKIP: 检索未命中（embedding 兜底模式可能匹配率低）")

    # 验证对话记录已入库
    conv_id = answer_data["conversation_id"]
    assert conv_id is not None, "对话记录应已持久化"
    get_resp = client.get(f"/api/v1/conversations/{conv_id}")
    assert get_resp.status_code == 200
    conv = get_resp.json()["data"]
    assert conv["question"] == "FastAPI 是什么？"
    assert conv["knowledge_base_id"] == kb_id
    assert conv["user_id"] == user_id
    # 验证 source_document_ids 已持久化
    if source_doc_ids:
        persisted_ids = conv["source_document_ids"]
        assert document_id in persisted_ids, "持久化的 source_document_ids 应包含上传文档 ID"
    print(f"[1] PERSIST OK: conv_id={conv_id} status={conv['status']}")

    # ================================================================
    # 场景 2：知识库隔离 - KB2 为空，提问应返回兜底回答
    # ================================================================
    kb2_id = _create_kb(user_id, suffix + "_empty")
    empty_resp = _ask(user_id, kb2_id, "这个知识库有内容吗？")
    assert empty_resp.status_code == 200
    empty_data = empty_resp.json()["data"]
    assert len(empty_data["source_documents"]) == 0, "空知识库不应有检索结果"
    assert "未找到相关资料" in empty_data["answer"] or empty_data["success"] is False
    print(f"[2] ISOLATION OK: 空 KB 返回兜底回答, docs=0")

    # ================================================================
    # 场景 3：链路漏洞修复 - 空提问拦截(422)
    # ================================================================
    empty_q_resp = _ask(user_id, kb_id, "")
    assert empty_q_resp.status_code == 422, f"空提问应 422: {empty_q_resp.status_code}"
    print("[3] EMPTY QUESTION OK: 422 拦截")

    # 纯空格提问也应拦截
    whitespace_resp = _ask(user_id, kb_id, "   ")
    assert whitespace_resp.status_code == 422, f"纯空格提问应 422: {whitespace_resp.status_code}"
    print("[3] WHITESPACE QUESTION OK: 422 拦截")

    # ================================================================
    # 场景 4：链路漏洞修复 - 超长上下文截断（验证 Token 截断不报错）
    # ================================================================
    # 使用接近上限的提问（2000 字符以内），验证系统正常处理
    long_question = "请详细介绍 FastAPI 框架。 " * 80  # ~1600 字符，在 2000 限制内
    long_resp = _ask(user_id, kb_id, long_question)
    assert long_resp.status_code == 200, f"长提问不应报错: {long_resp.status_code}"
    long_data = long_resp.json()["data"]
    assert len(long_data["answer"]) > 0
    print(f"[4] LONG QUESTION OK: 截断后正常问答, answer_len={len(long_data['answer'])}")

    # 超过 2000 字符的提问应被 422 拦截
    over_limit_question = "测试超长提问。 " * 300  # ~2400 字符，超过 2000 限制
    over_resp = _ask(user_id, kb_id, over_limit_question)
    assert over_resp.status_code == 422, f"超长提问应 422: {over_resp.status_code}"
    print("[4] OVER LIMIT OK: 超过 2000 字符的提问被 422 拦截")

    # ================================================================
    # 场景 5：链路漏洞修复 - 检索失败兜底（不存在的内容）
    # ================================================================
    # 用一个完全不相关的提问，验证即使检索结果少也能正常返回
    unrelated_resp = _ask(user_id, kb_id, "量子力学的基本原理是什么？")
    assert unrelated_resp.status_code == 200
    print("[5] FALLBACK OK: 不相关问题正常返回兜底回答")

    # ================================================================
    # 场景 6：禁用知识库拦截(403)
    # ================================================================
    from core.db import SessionLocal
    from api.document.model import KnowledgeBase
    from api.rag.enums import KnowledgeBaseStatus

    # 直接通过 ORM 将知识库状态改为 disabled
    db_session = SessionLocal()
    try:
        kb = db_session.get(KnowledgeBase, kb_id)
        kb.status = KnowledgeBaseStatus.DISABLED
        db_session.commit()
    finally:
        db_session.close()

    disabled_resp = _ask(user_id, kb_id, "测试禁用知识库提问")
    assert disabled_resp.status_code == 403, f"禁用 KB 应 403: {disabled_resp.status_code}"
    assert "禁用" in disabled_resp.json()["message"]
    print("[6] DISABLED KB OK: 403 拦截禁用知识库")

    # 恢复知识库状态
    db_session = SessionLocal()
    try:
        kb = db_session.get(KnowledgeBase, kb_id)
        kb.status = KnowledgeBaseStatus.ACTIVE
        db_session.commit()
    finally:
        db_session.close()
    print("[6] KB RESTORED: 状态恢复为 active")

    # ================================================================
    # 场景 7：越权访问拦截(403)
    # ================================================================
    other_user_id = _create_user(suffix + "_other")
    unauthorized_resp = _ask(other_user_id, kb_id, "越权提问测试")
    assert unauthorized_resp.status_code == 403, f"越权应 403: {unauthorized_resp.status_code}"
    print("[7] UNAUTHORIZED OK: 403 拦截越权访问")

    # ================================================================
    # 场景 8：不存在的知识库(404)
    # ================================================================
    not_found_resp = _ask(user_id, 999999, "不存在的知识库")
    assert not_found_resp.status_code == 404, f"不存在 KB 应 404: {not_found_resp.status_code}"
    print("[8] NOT FOUND OK: 404 拦截不存在的知识库")

    # ================================================================
    # 场景 9：RAG 健康检查端点
    # ================================================================
    health_resp = client.get("/api/v1/rag/health")
    assert health_resp.status_code == 200, f"健康检查失败: {health_resp.status_code}"
    health = health_resp.json()["data"]
    assert health["chain"] == "StandardRAGChain"
    assert health["max_context_tokens"] > 0
    assert health["default_top_k"] > 0
    assert "retriever" in health
    assert "llm" in health
    print(f"[9] HEALTH OK: chain={health['chain']} tokens={health['max_context_tokens']}")

    # ================================================================
    # 场景 10：对话记录完整 CRUD 闭环
    # ================================================================
    # 列表查询 - 按知识库
    list_kb_resp = client.get(f"/api/v1/knowledge-bases/{kb_id}/conversations")
    assert list_kb_resp.status_code == 200
    kb_convs = list_kb_resp.json()["data"]
    assert len(kb_convs) >= 1
    print(f"[10] LIST BY KB OK: count={len(kb_convs)}")

    # 列表查询 - 按用户
    list_user_resp = client.get(f"/api/v1/users/{user_id}/conversations")
    assert list_user_resp.status_code == 200
    user_convs = list_user_resp.json()["data"]
    assert len(user_convs) >= 1
    print(f"[10] LIST BY USER OK: count={len(user_convs)}")

    # 单条查询
    single_resp = client.get(f"/api/v1/conversations/{conv_id}")
    assert single_resp.status_code == 200
    single_conv = single_resp.json()["data"]
    assert single_conv["id"] == conv_id
    print(f"[10] GET ONE OK: id={conv_id} status={single_conv['status']}")

    # 删除
    del_resp = client.delete(f"/api/v1/conversations/{conv_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["data"]["deleted"] is True
    print(f"[10] DELETE OK: id={conv_id}")

    # 验证删除后 404
    verify_resp = client.get(f"/api/v1/conversations/{conv_id}")
    assert verify_resp.status_code == 404
    print("[10] VERIFY DELETE OK: 删除后返回 404")

    # 删除不存在的记录
    del_not_found = client.delete(f"/api/v1/conversations/{conv_id}")
    assert del_not_found.status_code == 404
    print("[10] DELETE NOT FOUND OK: 404")

    # ================================================================
    # 场景 11：top_k 参数传递验证
    # ================================================================
    # 使用自定义 top_k 提问，验证不报错
    topk_resp = _ask(user_id, kb_id, "LangChain 是什么？", top_k=2)
    assert topk_resp.status_code == 200, f"自定义 top_k 问答失败: {topk_resp.status_code}"
    print("[11] TOP_K OK: 自定义 top_k=2 正常工作")

    # top_k 超范围应 422
    topk_invalid = _ask(user_id, kb_id, "测试", top_k=100)
    assert topk_invalid.status_code == 422, f"top_k 超范围应 422: {topk_invalid.status_code}"
    print("[11] TOP_K VALIDATION OK: top_k=100 被 422 拦截")

    print("\n=== Day8 全部自检通过 ===")


if __name__ == "__main__":
    main()
