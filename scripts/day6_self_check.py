"""Day6 文档管理模块自检脚本。

验证链路：创建用户 -> 创建知识库 -> 上传 TXT -> 重复上传拦截 -> 删除文档 -> 验证删除。
"""

from __future__ import annotations

import io
from uuid import uuid4

from fastapi.testclient import TestClient

from core.db import create_all_tables, load_all_models
from init_app import app

client = TestClient(app)


def main() -> None:
    """执行 Day6 全链路自检。"""
    load_all_models()
    create_all_tables()

    suffix = uuid4().hex[:8]

    # 1. 创建用户
    user_resp = client.post(
        "/api/v1/auth/create_user",
        json={
            "username": f"day6_user_{suffix}",
            "email": f"day6_user_{suffix}@example.com",
            "password": "Password123",
        },
    )
    assert user_resp.status_code == 201, f"创建用户失败: {user_resp.json()}"
    user_id = user_resp.json()["data"]["id"]
    print(f"USER OK: id={user_id}")

    # 2. 创建知识库
    kb_resp = client.post(
        "/api/v1/knowledge-bases",
        json={"owner_id": user_id, "name": f"Day6KB-{suffix}", "description": "Day6 测试知识库"},
    )
    assert kb_resp.status_code == 201, f"创建知识库失败: {kb_resp.json()}"
    kb_id = kb_resp.json()["data"]["id"]
    print(f"KB OK: id={kb_id}")

    # 3. 上传 TXT 文件
    txt_content = (
        "FastAPI 是一个现代、快速的 Python Web 框架，用于构建 API。"
        "它基于标准 Python 类型提示，支持自动文档生成。"
        "Qdrant 是一个高性能向量数据库，支持相似度检索。"
        "LangChain 是一个用于构建 LLM 应用的框架，提供了检索、问答等能力。"
        "通过将文档切片后存入向量库，可以实现基于语义的精准检索。"
    )
    files = {"file": ("day6_test.txt", io.BytesIO(txt_content.encode("utf-8")), "text/plain")}
    upload_resp = client.post(f"/api/v1/knowledge-bases/documents/upload/{kb_id}", files=files)
    assert upload_resp.status_code == 201, f"上传文档失败: {upload_resp.json()}"
    upload_data = upload_resp.json()["data"]
    document_id = upload_data["document"]["id"]
    chunk_count = upload_data["chunk_count"]
    assert upload_data["document"]["parse_status"] == "success"
    assert chunk_count > 0
    assert len(upload_data["vector_ids"]) == chunk_count
    print(f"UPLOAD OK: id={document_id} chunks={chunk_count} vectors={len(upload_data['vector_ids'])}")

    # 4. 重复上传拦截
    files2 = {"file": ("day6_test_copy.txt", io.BytesIO(txt_content.encode("utf-8")), "text/plain")}
    dup_resp = client.post(f"/api/v1/knowledge-bases/documents/upload/{kb_id}", files=files2)
    assert dup_resp.status_code == 409, f"重复上传应被拦截: {dup_resp.json()}"
    print(f"DEDUP OK: {dup_resp.json()['message']}")

    # 5. 查询文档列表
    list_resp = client.post("/api/v1/knowledge-bases/documents/list", json={"knowledge_base_id": kb_id})
    assert list_resp.status_code == 200
    docs = list_resp.json()["data"]
    assert len(docs) == 1
    print(f"LIST OK: {len(docs)} document(s)")

    # 6. 删除文档
    del_resp = client.delete(f"/api/v1/documents/{document_id}")
    assert del_resp.status_code == 200, f"删除文档失败: {del_resp.json()}"
    print(f"DELETE OK: {del_resp.json()['message']}")

    # 7. 验证删除后列表为空
    list_resp2 = client.post("/api/v1/knowledge-bases/documents/list", json={"knowledge_base_id": kb_id})
    assert list_resp2.status_code == 200
    docs2 = list_resp2.json()["data"]
    assert len(docs2) == 0
    print("VERIFY OK: 文档删除后列表为空")

    # 8. 不支持的文件类型拦截
    files3 = {"file": ("test.docx", io.BytesIO(b"test"), "application/octet-stream")}
    bad_resp = client.post(f"/api/v1/knowledge-bases/documents/upload/{kb_id}", files=files3)
    assert bad_resp.status_code == 400, f"不支持的类型应被拦截: {bad_resp.json()}"
    print(f"TYPE CHECK OK: {bad_resp.json()['message']}")

    print("\n=== Day6 全部自检通过 ===")


if __name__ == "__main__":
    main()
