"""Day6 文档管理模块自检脚本。

验证链路：创建用户 -> 登录 -> 创建知识库 -> 上传文件 -> 创建文档 -> 解析入库
-> 重复上传拦截 -> 查询切片/文档列表 -> 删除文档 -> 验证删除 -> 文件类型拦截。

说明：接口已在 Day7 重构为 files / documents 两段式，本脚本已同步适配：
- API 前缀为 /api（见 .env 的 API_PREFIX）；
- 业务接口需携带登录签发的 Bearer JWT；
- 向量化在解析后台任务（process_file）中完成，需 Qdrant 服务可用。
"""

from __future__ import annotations

import io
import time
from uuid import uuid4

from fastapi.testclient import TestClient

from api.document.enums import DocumentParseStatus
from core.db import create_all_tables, load_all_models
from init_app import app

client = TestClient(app)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def main() -> None:
    """执行 Day6 全链路自检。"""
    load_all_models()
    create_all_tables()

    suffix = uuid4().hex[:8]

    # 1. 创建用户（注册接口免鉴权）
    user_resp = client.post(
        "/api/auth/create_user",
        json={
            "username": f"day6_user_{suffix}",
            "email": f"day6_user_{suffix}@example.com",
            "password": "Password123",
        },
    )
    assert user_resp.status_code == 201, f"创建用户失败: {user_resp.json()}"
    user_id = user_resp.json()["data"]["id"]
    print(f"USER OK: id={user_id}")

    # 2. 登录签发 JWT（业务接口统一鉴权）
    login_resp = client.post(
        "/api/auth/login",
        json={"username": f"day6_user_{suffix}", "password": "Password123"},
    )
    assert login_resp.status_code == 200, f"登录失败: {login_resp.json()}"
    token = login_resp.json()["data"]["accessToken"]
    headers = _headers(token)
    print("LOGIN OK: 已签发 JWT")

    # 3. 创建知识库（owner 从令牌解析，无需传 owner_id）
    kb_resp = client.post(
        "/api/knowledge-bases/create",
        headers=headers,
        json={"name": f"Day6KB-{suffix}", "description": "Day6 测试知识库"},
    )
    assert kb_resp.status_code == 201, f"创建知识库失败: {kb_resp.json()}"
    kb_id = kb_resp.json()["data"]["id"]
    print(f"KB OK: id={kb_id}")

    # 4. 上传 TXT 文件（仅落盘并记录 FileRecord，尚未向量化）
    txt_content = (
        "FastAPI 是一个现代、快速的 Python Web 框架，用于构建 API。"
        "它基于标准 Python 类型提示，支持自动文档生成。"
        "Qdrant 是一个高性能向量数据库，支持相似度检索。"
        "LangChain 是一个用于构建 LLM 应用的框架，提供了检索、问答等能力。"
        "通过将文档切片后存入向量库，可以实现基于语义的精准检索。"
    )
    files = {"files": ("day6_test.txt", io.BytesIO(txt_content.encode("utf-8")), "text/plain")}
    upload_resp = client.post("/api/files/upload", headers=headers, files=files)
    assert upload_resp.status_code == 201, f"上传文件失败: {upload_resp.json()}"
    results = upload_resp.json()["data"]
    assert results[0]["accepted"] is True, f"文件应被接受: {results}"
    file_id = results[0]["fileId"]
    print(f"UPLOAD OK: file_id={file_id}")

    # 5. 重复上传拦截（MD5 去重：accepted=false 而非 409）
    files2 = {"files": ("day6_test_copy.txt", io.BytesIO(txt_content.encode("utf-8")), "text/plain")}
    dup_resp = client.post("/api/files/upload", headers=headers, files=files2)
    assert dup_resp.status_code == 201, f"重复上传响应异常: {dup_resp.json()}"
    dup_result = dup_resp.json()["data"][0]
    assert dup_result["accepted"] is False, f"重复上传应被拒绝: {dup_result}"
    assert "已上传" in dup_result["error"], f"重复上传提示异常: {dup_result}"
    print(f"DEDUP OK: {dup_result['error']}")

    # 6. 创建文档（file + knowledge_base 关联，parse_status=pending）
    doc_resp = client.post(
        "/api/documents/create",
        headers=headers,
        json={"file_id": file_id, "knowledge_base_id": kb_id, "title": "Day6 测试文档"},
    )
    assert doc_resp.status_code == 201, f"创建文档失败: {doc_resp.json()}"
    document_id = doc_resp.json()["data"]["id"]
    print(f"DOCUMENT OK: id={document_id}")

    # 7. 触发解析（后台任务：解析 -> 切片 -> 向量化 -> 写入 Qdrant）
    parse_resp = client.post("/api/documents/parse", headers=headers, json={"file_id": file_id})
    assert parse_resp.status_code == 200, f"触发解析失败: {parse_resp.json()}"
    print("PARSE QUEUED OK")

    # 8. 轮询解析状态直至成功（后台任务为异步执行）
    deadline = time.monotonic() + 30
    while True:
        detail_resp = client.post(
            "/api/documents/detail", headers=headers, json={"document_id": document_id}
        )
        assert detail_resp.status_code == 200, f"查询文档失败: {detail_resp.json()}"
        doc = detail_resp.json()["data"]
        if doc["parseStatus"] == DocumentParseStatus.SUCCESS:
            break
        if doc["parseStatus"] == DocumentParseStatus.FAILED:
            raise AssertionError(f"解析失败: {doc['errorMsg']}")
        assert time.monotonic() < deadline, f"解析超时: {doc}"
        time.sleep(0.5)
    assert doc["chunkCount"] > 0, f"切片数量应大于 0: {doc}"
    print(f"PARSE OK: chunks={doc['chunkCount']} vector_cleaned={doc['vectorCleaned']}")

    # 9. 查询切片内容
    chunks_resp = client.post(
        "/api/documents/chunks", headers=headers, json={"document_id": document_id}
    )
    assert chunks_resp.status_code == 200, f"查询切片失败: {chunks_resp.json()}"
    chunks = chunks_resp.json()["data"]["items"]
    assert chunks, "切片列表不应为空"
    print(f"CHUNKS OK: {len(chunks)} chunk(s)")

    # 10. 查询文档列表
    list_resp = client.post(
        "/api/documents/list", headers=headers, json={"knowledge_base_id": kb_id}
    )
    assert list_resp.status_code == 200, f"查询文档列表失败: {list_resp.json()}"
    docs = list_resp.json()["data"]["items"]
    assert len(docs) == 1, f"应只有 1 个文档: {docs}"
    print(f"LIST OK: {len(docs)} document(s)")

    # 11. 删除文档（软删除 + 异步清理向量）
    del_resp = client.post(
        "/api/documents/delete", headers=headers, json={"document_id": document_id}
    )
    assert del_resp.status_code == 200, f"删除文档失败: {del_resp.json()}"
    assert del_resp.json()["data"]["vectorCleanupQueued"] is True, "应排队清理向量"
    print(f"DELETE OK: {del_resp.json()['message']}")

    # 12. 验证删除后列表为空
    list_resp2 = client.post(
        "/api/documents/list", headers=headers, json={"knowledge_base_id": kb_id}
    )
    assert list_resp2.status_code == 200
    docs2 = list_resp2.json()["data"]["items"]
    assert len(docs2) == 0, f"删除后列表应为空: {docs2}"
    print("VERIFY OK: 文档删除后列表为空")

    # 13. 不支持的文件类型拦截（.env 允许 txt/pdf，docx 应被拒绝）
    files3 = {"files": ("test.docx", io.BytesIO(b"test"), "application/octet-stream")}
    bad_resp = client.post("/api/files/upload", headers=headers, files=files3)
    assert bad_resp.status_code == 201, f"非法类型响应异常: {bad_resp.json()}"
    bad_result = bad_resp.json()["data"][0]
    assert bad_result["accepted"] is False, f"非法类型应被拒绝: {bad_result}"
    print(f"TYPE CHECK OK: {bad_result['error']}")

    print("\n=== Day6 全部自检通过 ===")


if __name__ == "__main__":
    main()
