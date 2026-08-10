"""Day11 LangChain 流式问答自检脚本：SSE 打字机效果全链路验证。

验证目标：
1. SSE 端点规范：/conversations/ask/stream 返回 text/event-stream + UTF-8 响应头
2. 事件序列稳定：sources -> chunk* -> (error?) -> done，done 恒为最后事件且携带 conversation_id
3. 中文无乱码：SSE data 行以 UTF-8 直出中文，无 Unicode 转义观感问题
4. 对话记录异步入库：流结束后落库成功，GET 详情可查到完整问答内容
5. LLM 流式中断兜底：error 事件 + done(success=False)，仍以 FAILED 状态落库可追溯
6. 流前校验兜底：用户不存在 404 / 禁用知识库 403 / 超长提问 422 均为统一 JSON 格式
7. 无检索结果兜底：空知识库提问以兜底文案流式推送，done(success=True)
8. 真实链路稳定：不依赖任何打桩的端到端流式调用，无论 LLM 是否可用均稳定收尾

说明：
- 场景 3/4/5 使用打桩 LLM 流式方法，保证离线环境结果确定。
- 场景 8 不依赖打桩，容忍 LLM 不可用走 error 兜底，仅验证流协议稳定性。
"""

from __future__ import annotations

import io
import json
from uuid import uuid4

from fastapi.testclient import TestClient

from core.db import SessionLocal, create_all_tables, load_all_models
from core.langchain.llm import LLMInvocationError
from core.langchain.rag_chain import get_rag_chain
from init_app import app

client = TestClient(app)

STREAM_URL = "/api/v1/conversations/ask/stream"


def _create_user(suffix: str) -> int:
    resp = client.post(
        "/api/v1/users",
        json={
            "username": f"day11_user_{suffix}",
            "email": f"day11_user_{suffix}@example.com",
            "password": "Password123",
        },
    )
    assert resp.status_code == 201, f"创建用户失败: {resp.json()}"
    return resp.json()["data"]["id"]


def _create_kb(user_id: int, suffix: str) -> int:
    resp = client.post(
        "/api/v1/knowledge-bases",
        json={"owner_id": user_id, "name": f"Day11KB-{suffix}", "description": "Day11 测试知识库"},
    )
    assert resp.status_code == 201, f"创建知识库失败: {resp.json()}"
    return resp.json()["data"]["id"]


def _upload_txt(kb_id: int, content: str, filename: str):
    files = {"file": (filename, io.BytesIO(content.encode("utf-8")), "text/plain")}
    return client.post(f"/api/v1/knowledge-bases/documents/upload/{kb_id}", files=files)


def _parse_sse_events(body: str) -> list[dict]:
    """把 SSE 响应体解析为事件字典列表（data: 行，JSON 载荷）。"""
    events = []
    for block in body.split("\n\n"):
        block = block.strip()
        if not block.startswith("data:"):
            continue
        events.append(json.loads(block[len("data:"):].strip()))
    return events


def _patch_llm_stream(stream_func) -> None:
    """替换全局 RAG 链 LLM 客户端的流式方法（测试打桩）。"""
    get_rag_chain()._llm_client.stream_with_messages = stream_func


def main() -> None:
    """执行 Day11 流式问答自检。"""
    load_all_models()
    create_all_tables()

    suffix = uuid4().hex[:8]
    rag_chain = get_rag_chain()
    original_stream = rag_chain._llm_client.stream_with_messages

    # ================================================================
    # 准备：用户 + 知识库 + 文档
    # ================================================================
    user_id = _create_user(suffix)
    kb_id = _create_kb(user_id, suffix)
    txt_content = (
        "FastAPI 是一个现代的 Python Web 框架，支持自动文档生成。"
        "Chroma 是一个轻量级的向量数据库，支持本地持久化存储。"
        "LangChain 提供了检索、问答等 RAG 核心能力的封装。"
    )
    resp = _upload_txt(kb_id, txt_content, f"day11_{suffix}.txt")
    assert resp.status_code == 201, f"上传文档失败: {resp.json()}"

    # ================================================================
    # 场景 1：SSE 端点规范（Content-Type + 禁缓存响应头）
    # ================================================================
    fake_chunks = ["这是", "流式", "打字机", "回答。"]

    def fake_stream(messages):
        for piece in fake_chunks:
            yield piece

    try:
        _patch_llm_stream(fake_stream)
        resp = client.post(
            STREAM_URL,
            json={"user_id": user_id, "knowledge_base_id": kb_id, "question": "FastAPI 是什么？"},
        )
    finally:
        _patch_llm_stream(original_stream)

    assert resp.status_code == 200, f"流式接口应 200: {resp.status_code}"
    content_type = resp.headers.get("content-type", "")
    assert content_type.startswith("text/event-stream"), f"Content-Type 应为 SSE: {content_type}"
    assert "charset=utf-8" in content_type.lower(), f"SSE 应声明 UTF-8: {content_type}"
    assert resp.headers.get("cache-control") == "no-cache", "SSE 应禁止缓存"
    print("[1] SSE HEADERS OK: text/event-stream + UTF-8 + no-cache")

    # ================================================================
    # 场景 2：事件序列稳定（sources -> chunk* -> done）
    # ================================================================
    events = _parse_sse_events(resp.text)
    assert len(events) >= 3, f"事件数不足: {len(events)}"
    assert events[0]["event"] == "sources", "首个事件应为 sources"
    assert len(events[0]["source_documents"]) >= 1, "应命中至少一条源文档"
    assert events[-1]["event"] == "done", "最后事件应为 done"
    done_event = events[-1]
    assert done_event["success"] is True, f"打桩流应成功: {done_event}"
    assert done_event["conversation_id"] is not None, "done 应携带 conversation_id"

    chunk_events = [ev for ev in events if ev["event"] == "chunk"]
    assert len(chunk_events) == len(fake_chunks), "chunk 事件数应与打桩块数一致"
    reassembled = "".join(ev["content"] for ev in chunk_events)
    assert reassembled == "".join(fake_chunks), "chunk 拼接结果应与完整回答一致"
    assert done_event["answer"] == reassembled, "done.answer 应与 chunk 拼接一致"
    print(f"[2] EVENT SEQUENCE OK: sources -> {len(chunk_events)} chunks -> done")

    # ================================================================
    # 场景 3：中文 UTF-8 直出无乱码（无 Unicode 转义）
    # ================================================================
    assert "流式" in resp.text, "响应体应直出中文，而非转义序列"
    assert "\\u6d41" not in resp.text, "SSE 载荷不应出现 Unicode 转义乱码观感"
    print("[3] UTF-8 OK: 中文直出无转义乱码")

    # ================================================================
    # 场景 4：对话记录流后落库，详情可查
    # ================================================================
    conversation_id = done_event["conversation_id"]
    detail_resp = client.get(f"/api/v1/conversations/{conversation_id}")
    assert detail_resp.status_code == 200, f"对话详情应 200: {detail_resp.status_code}"
    detail = detail_resp.json()["data"]
    assert detail["answer"] == reassembled, "落库回答应与流式完整回答一致"
    assert detail["question"] == "FastAPI 是什么？"
    assert detail["status"] == "generated", f"成功流应落 GENERATED 状态: {detail['status']}"
    assert detail["source_document_ids"], "落库应包含溯源文档 ID"
    print(f"[4] PERSIST OK: conversation_id={conversation_id} 落库内容完整")

    # ================================================================
    # 场景 5：LLM 流式中断兜底（error + done(success=False) + FAILED 落库）
    # ================================================================
    def broken_stream(messages):
        raise LLMInvocationError("simulated stream failure")

    try:
        _patch_llm_stream(broken_stream)
        resp = client.post(
            STREAM_URL,
            json={"user_id": user_id, "knowledge_base_id": kb_id, "question": "Chroma 是什么？"},
        )
    finally:
        _patch_llm_stream(original_stream)

    assert resp.status_code == 200, "流式中断也应 200 收尾，不允许裸断连接"
    events = _parse_sse_events(resp.text)
    event_names = [ev["event"] for ev in events]
    assert "error" in event_names, "LLM 中断应推送 error 事件"
    assert events[-1]["event"] == "done", "中断后 done 仍应为最后事件"
    assert events[-1]["success"] is False, "中断流 done.success 应为 False"
    failed_conversation_id = events[-1]["conversation_id"]
    assert failed_conversation_id is not None, "失败流也应落库以便追溯"

    detail_resp = client.get(f"/api/v1/conversations/{failed_conversation_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["data"]["status"] == "failed", "中断流应落 FAILED 状态"
    print("[5] STREAM ERROR OK: error 兜底 + done 收尾 + FAILED 落库")

    # ================================================================
    # 场景 6：流前校验兜底（404 / 403 / 422 统一 JSON，不进入 SSE）
    # ================================================================
    resp = client.post(
        STREAM_URL,
        json={"user_id": 999999, "knowledge_base_id": kb_id, "question": "任意问题"},
    )
    assert resp.status_code == 404, f"用户不存在应 404: {resp.status_code}"
    assert resp.json()["code"] != 0, "404 应为统一失败格式"

    from api.knowledge.enums import KnowledgeBaseStatus
    from api.knowledge.model import KnowledgeBase

    db_session = SessionLocal()
    try:
        kb = db_session.get(KnowledgeBase, kb_id)
        kb.status = KnowledgeBaseStatus.DISABLED
        db_session.commit()
    finally:
        db_session.close()

    resp = client.post(
        STREAM_URL,
        json={"user_id": user_id, "knowledge_base_id": kb_id, "question": "任意问题"},
    )
    assert resp.status_code == 403, f"禁用 KB 应 403: {resp.status_code}"
    assert "禁用" in resp.json()["message"], "403 文案应提示知识库禁用"

    db_session = SessionLocal()
    try:
        kb = db_session.get(KnowledgeBase, kb_id)
        kb.status = KnowledgeBaseStatus.ACTIVE
        db_session.commit()
    finally:
        db_session.close()

    resp = client.post(
        STREAM_URL,
        json={"user_id": user_id, "knowledge_base_id": kb_id, "question": "长" * 2001},
    )
    assert resp.status_code == 422, f"超长提问应 422: {resp.status_code}"
    print("[6] PRE-STREAM VALIDATION OK: 404/403/422 统一 JSON 拦截")

    # ================================================================
    # 场景 7：无检索结果兜底（空知识库流式推送兜底文案）
    # ================================================================
    empty_kb_id = _create_kb(user_id, f"{suffix}_empty")
    resp = client.post(
        STREAM_URL,
        json={"user_id": user_id, "knowledge_base_id": empty_kb_id, "question": "随便问点什么？"},
    )
    assert resp.status_code == 200, f"空知识库流式应 200: {resp.status_code}"
    events = _parse_sse_events(resp.text)
    assert events[0]["event"] == "sources" and not events[0]["source_documents"]
    chunk_text = "".join(ev["content"] for ev in events if ev["event"] == "chunk")
    assert "未找到相关资料" in chunk_text, f"无检索结果应流式推送兜底文案: {chunk_text}"
    assert events[-1]["event"] == "done" and events[-1]["success"] is True
    print("[7] NO-CONTEXT OK: 空知识库兜底文案流式推送")

    # ================================================================
    # 场景 8：真实链路端到端稳定（不打桩，容忍 LLM 不可用走兜底）
    # ================================================================
    resp = client.post(
        STREAM_URL,
        json={"user_id": user_id, "knowledge_base_id": kb_id, "question": "LangChain 提供哪些能力？"},
    )
    assert resp.status_code == 200, f"真实流式调用应 200: {resp.status_code}"
    events = _parse_sse_events(resp.text)
    assert events, "真实链路应至少产出事件"
    assert events[0]["event"] == "sources", "真实链路首事件应为 sources"
    assert events[-1]["event"] == "done", "真实链路必须以 done 收尾"
    assert events[-1]["conversation_id"] is not None, "真实链路必须落库"
    print(
        f"[8] E2E OK: 真实链路流式稳定收尾 success={events[-1]['success']} "
        f"chunks={sum(1 for ev in events if ev['event'] == 'chunk')}"
    )

    print("\n=== Day11 全部自检通过 ===")


if __name__ == "__main__":
    main()
