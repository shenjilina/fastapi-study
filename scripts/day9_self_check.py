"""Day9 全局异常兜底 + 接口标准化 + BUG 全修复自检脚本。

验证目标：
1. 统一响应格式：所有正常/异常接口均返回 {code, message, data} 结构
2. 全局异常兜底：未知路由 404、方法不允许 405、参数校验 422 均对齐统一格式
3. 边界异常：空文件、超大文件、不支持类型、重复上传均正确拦截
4. 数据库事务回滚：模拟状态落库失败，验证向量数据同步回滚且文档置为 FAILED
5. RAG 链路兜底：LLM 不可用时接口仍返回 200 与兜底回答
6. 所有响应统一携带 X-Request-ID 头

说明：本脚本不依赖 Ollama 可用，LLM 异常时走兜底回答，链路仍完整打通。
"""

from __future__ import annotations

import io
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from api.document import crud as document_crud
from config.settings import get_settings
from core.db import create_all_tables, load_all_models
from core.langchain.qdrant_store import get_qdrant_store
from init_app import app

client = TestClient(app)


def _assert_unified_format(resp, *, expect_code_zero: bool | None = None) -> dict:
    """断言响应体符合统一格式，并返回响应体。"""
    body = resp.json()
    assert set(body.keys()) >= {"code", "message", "data"}, f"响应缺少统一字段: {body}"
    if expect_code_zero is True:
        assert body["code"] == 0, f"期望 code=0, 实际: {body}"
    if expect_code_zero is False:
        assert body["code"] != 0, f"期望非 0 code, 实际: {body}"
    return body


def _assert_request_id(resp) -> None:
    """断言响应头携带 X-Request-ID。"""
    assert resp.headers.get("X-Request-ID"), "响应缺少 X-Request-ID 头"


def _create_user(suffix: str) -> tuple[int, dict]:
    """创建用户并登录，返回 (user_id, 鉴权请求头)。"""
    username = f"day9_user_{suffix}"
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
    login_resp = client.post("/api/v1/auth/login", json={"username": username, "password": "Password123"})
    assert login_resp.status_code == 200, f"登录失败: {login_resp.json()}"
    token = login_resp.json()["data"]["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def _create_kb(user_id: int, suffix: str) -> int:
    resp = client.post(
        "/api/v1/knowledge-bases",
        json={"owner_id": user_id, "name": f"Day9KB-{suffix}", "description": "Day9 测试知识库"},
    )
    assert resp.status_code == 201, f"创建知识库失败: {resp.json()}"
    return resp.json()["data"]["id"]


def _upload_txt(kb_id: int, content: str, filename: str = "day9_doc.txt"):
    files = {"file": (filename, io.BytesIO(content.encode("utf-8")), "text/plain")}
    return client.post(f"/api/v1/knowledge-bases/documents/upload/{kb_id}", files=files)


def main() -> None:
    """执行 Day9 全接口自检。"""
    load_all_models()
    create_all_tables()

    suffix = uuid4().hex[:8]

    # ================================================================
    # 场景 1：全局异常兜底 - 未知路由 404 对齐统一格式
    # ================================================================
    resp = client.get("/api/v1/not-exists-route")
    assert resp.status_code == 404
    body = _assert_unified_format(resp, expect_code_zero=False)
    assert "不存在" in body["message"], f"404 文案不符合预期: {body['message']}"
    _assert_request_id(resp)
    print("[1] UNKNOWN ROUTE OK: 404 统一格式 + request_id 头")

    # ================================================================
    # 场景 2：全局异常兜底 - 方法不允许 405 对齐统一格式
    # ================================================================
    resp = client.delete("/api/v1/users/list")
    assert resp.status_code == 405
    body = _assert_unified_format(resp, expect_code_zero=False)
    _assert_request_id(resp)
    print("[2] METHOD NOT ALLOWED OK: 405 统一格式")

    # ================================================================
    # 场景 3：参数校验 422 统一格式（缺字段 + 非法字段）
    # ================================================================
    resp = client.post("/api/v1/auth/create_user", json={"username": "x"})
    assert resp.status_code == 422
    body = _assert_unified_format(resp, expect_code_zero=False)
    assert body["code"] == 1001, f"校验错误 code 应为 1001: {body['code']}"
    assert "errors" in body["data"], "422 响应应包含 errors 明细"
    _assert_request_id(resp)
    print("[3] VALIDATION 422 OK: 统一格式 + errors 明细")

    # ================================================================
    # 场景 4：正常链路统一响应格式（用户 -> 知识库 -> 文档 -> 问答）
    # ================================================================
    user_id, headers = _create_user(suffix)
    kb_id = _create_kb(user_id, suffix)

    txt_content = (
        "FastAPI 是一个现代的 Python Web 框架，支持自动文档生成。"
        "Qdrant 是一个高性能向量数据库，支持相似度检索。"
        "LangChain 提供了检索、问答等 RAG 核心能力的封装。"
    )
    resp = _upload_txt(kb_id, txt_content)
    assert resp.status_code == 201, f"上传文档失败: {resp.json()}"
    body = _assert_unified_format(resp, expect_code_zero=True)
    document_id = body["data"]["document"]["id"]
    assert body["data"]["chunk_count"] >= 1
    _assert_request_id(resp)
    print(f"[4] UPLOAD OK: doc_id={document_id} chunks={body['data']['chunk_count']}")

    # ================================================================
    # 场景 5：边界异常 - 空文件上传拦截(422)
    # ================================================================
    resp = _upload_txt(kb_id, "", filename=f"empty_{suffix}.txt")
    assert resp.status_code == 422, f"空文件应 422: {resp.status_code}"
    _assert_unified_format(resp, expect_code_zero=False)
    print("[5] EMPTY FILE OK: 422 拦截空文件")

    # ================================================================
    # 场景 6：边界异常 - 不支持的文件类型(400)
    # ================================================================
    files = {"file": (f"bad_{suffix}.exe", io.BytesIO(b"MZ\x00\x00"), "application/octet-stream")}
    resp = client.post(f"/api/v1/knowledge-bases/documents/upload/{kb_id}", files=files)
    assert resp.status_code == 400, f"不支持类型应 400: {resp.status_code}"
    _assert_unified_format(resp, expect_code_zero=False)
    print("[6] UNSUPPORTED TYPE OK: 400 拦截")

    # ================================================================
    # 场景 7：边界异常 - 超大文件上传(413)
    # ================================================================
    settings = get_settings()
    original_limit = settings.max_upload_size_mb
    try:
        # 临时收紧上传限制为 1MB，上传 1.5MB 文件触发 413。
        settings.max_upload_size_mb = 1
        big_content = "超长文本内容。" * 200_000  # 约 1.4MB
        resp = _upload_txt(kb_id, big_content, filename=f"big_{suffix}.txt")
        assert resp.status_code == 413, f"超大文件应 413: {resp.status_code}"
        _assert_unified_format(resp, expect_code_zero=False)
    finally:
        settings.max_upload_size_mb = original_limit
    print("[7] OVERSIZE FILE OK: 413 拦截超大文件")

    # ================================================================
    # 场景 8：边界异常 - 重复文档上传(409)
    # ================================================================
    resp = _upload_txt(kb_id, txt_content)
    assert resp.status_code == 409, f"重复上传应 409: {resp.status_code}"
    _assert_unified_format(resp, expect_code_zero=False)
    print("[8] DUPLICATE FILE OK: 409 拦截重复文档")

    # ================================================================
    # 场景 9：BUG 修复 - 状态落库失败时向量同步回滚
    # ================================================================
    vector_store = get_qdrant_store()
    count_before = vector_store.count()

    original_update = document_crud.update_document_status
    call_counter = {"n": 0}

    def failing_update(db, *, document_id, parse_status, chunk_count=None):
        # 首次调用（SUCCESS 落库）模拟数据库故障，后续恢复。
        call_counter["n"] += 1
        if call_counter["n"] == 1:
            raise SQLAlchemyError("simulated DB failure")
        return original_update(
            db,
            document_id=document_id,
            parse_status=parse_status,
            chunk_count=chunk_count,
        )

    rollback_content = f"用于验证向量回滚的独立文档内容 {suffix}。" * 20
    try:
        document_crud.update_document_status = failing_update
        resp = _upload_txt(kb_id, rollback_content, filename=f"rollback_{suffix}.txt")
    finally:
        document_crud.update_document_status = original_update

    assert resp.status_code == 500, f"状态落库失败应 500: {resp.status_code}"
    _assert_unified_format(resp, expect_code_zero=False)

    count_after = vector_store.count()
    assert count_after == count_before, (
        f"向量未回滚: before={count_before} after={count_after}"
    )

    # 文档应被标记为 FAILED
    list_resp = client.post("/api/v1/knowledge-bases/documents/list", json={"knowledge_base_id": kb_id})
    assert list_resp.status_code == 200
    docs = list_resp.json()["data"]
    failed_docs = [
        item for item in docs
        if item["filename"] == f"rollback_{suffix}.txt"
    ]
    assert len(failed_docs) == 1, "回滚测试文档应存在记录"
    assert failed_docs[0]["parse_status"] == "failed", (
        f"文档状态应为 failed: {failed_docs[0]['parse_status']}"
    )
    print("[9] VECTOR ROLLBACK OK: 向量回滚 + 文档置 FAILED + 事务回滚")

    # ================================================================
    # 场景 10：RAG 链路兜底 - LLM 不可用时接口不 500
    # ================================================================
    ask_resp = client.post(
        "/api/v1/conversations/ask",
        headers=headers,
        json={"user_id": user_id, "knowledge_base_id": kb_id, "question": "FastAPI 是什么？"},
    )
    assert ask_resp.status_code == 200, f"问答接口应 200: {ask_resp.status_code}"
    ask_body = _assert_unified_format(ask_resp, expect_code_zero=True)
    assert len(ask_body["data"]["answer"]) > 0, "兜底回答不应为空"
    _assert_request_id(ask_resp)
    print(
        f"[10] RAG FALLBACK OK: success={ask_body['data']['success']} "
        f"answer_len={len(ask_body['data']['answer'])}"
    )

    # ================================================================
    # 场景 11：健康检查与根路由统一格式
    # ================================================================
    for path in ("/health", "/api/v1/rag/health"):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} 失败: {resp.status_code}"
        _assert_unified_format(resp, expect_code_zero=True)
        _assert_request_id(resp)
    print("[11] HEALTH OK: /health 与 /rag/health 统一格式")

    # ================================================================
    # 场景 12：登录接口统一格式（正常 + 异常）
    # ================================================================
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": f"day9_user_{suffix}", "password": "Password123"},
    )
    assert resp.status_code == 200
    _assert_unified_format(resp, expect_code_zero=True)

    resp = client.post(
        "/api/v1/auth/login",
        json={"username": f"day9_user_{suffix}", "password": "WrongPass123"},
    )
    assert resp.status_code == 401
    _assert_unified_format(resp, expect_code_zero=False)
    _assert_request_id(resp)
    print("[12] LOGIN OK: 正常登录 200 / 错误密码 401 均为统一格式")

    # ================================================================
    # 场景 13：资源删除闭环统一格式
    # ================================================================
    resp = client.delete(f"/api/v1/documents/{document_id}")
    assert resp.status_code == 200
    _assert_unified_format(resp, expect_code_zero=True)

    resp = client.delete(f"/api/v1/documents/{document_id}")
    assert resp.status_code == 404
    _assert_unified_format(resp, expect_code_zero=False)
    print("[13] DELETE OK: 删除 200 / 重复删除 404 均为统一格式")

    print("\n=== Day9 全部自检通过 ===")


if __name__ == "__main__":
    main()
