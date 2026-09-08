"""Day10 RAG 精度优化自检脚本：参数调优 + Prompt 升级 + 检索优化 + 前后对比。

验证目标：
1. 参数调优生效：chunk_size=400 / chunk_overlap=80 / top_k=5 / 阈值 1.2
2. Prompt 升级：引用序号规范、无关问题拒绝、结论先行结构
3. 检索优化：带分数检索、距离阈值过滤、近似切片去重（合成数据确定性验证）
4. 优化前后对比实验：旧参数(500/50) vs 新参数(400/80) 在相同语料与问题集上的
   检索命中率（hit rate / top1 命中率 / 平均排名）对比，固化最优参数依据

说明：
- 场景 4 的过滤/去重验证使用合成检索结果，不依赖嵌入模型质量，结果确定。
- 场景 5 的对比实验使用独立临时向量库目录，不污染主向量库。
"""

from __future__ import annotations

import io
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config.settings import get_settings
from core.db import create_all_tables, load_all_models
from core.langchain.rag_chain import SYSTEM_PROMPT_TEMPLATE, StandardRAGChain
from init_app import app

client = TestClient(app)


def _create_user(suffix: str) -> tuple[int, dict]:
    """创建用户并登录，返回 (user_id, 鉴权请求头)。"""
    username = f"day10_user_{suffix}"
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
        json={"owner_id": user_id, "name": f"Day10KB-{suffix}", "description": "Day10 测试知识库"},
    )
    assert resp.status_code == 201, f"创建知识库失败: {resp.json()}"
    return resp.json()["data"]["id"]


def main() -> None:
    """执行 Day10 精度优化自检与对比实验。"""
    load_all_models()
    create_all_tables()

    suffix = uuid4().hex[:8]
    settings = get_settings()

    # ================================================================
    # 场景 1：调优参数已生效（配置 + 健康检查端点）
    # ================================================================
    assert settings.chunk_size == 400, f"chunk_size 应为 400: {settings.chunk_size}"
    assert settings.chunk_overlap == 80, f"chunk_overlap 应为 80: {settings.chunk_overlap}"
    assert settings.retrieval_top_k == 5, f"retrieval_top_k 应为 5: {settings.retrieval_top_k}"
    assert settings.retrieval_score_threshold == 1.2, (
        f"retrieval_score_threshold 应为 1.2: {settings.retrieval_score_threshold}"
    )

    health_resp = client.get("/api/v1/rag/health")
    assert health_resp.status_code == 200
    health = health_resp.json()["data"]
    assert health["default_top_k"] == 5
    assert health["score_threshold"] == 1.2
    print("[1] PARAMS OK: chunk=400/80 top_k=5 threshold=1.2 已在配置与健康检查生效")

    # ================================================================
    # 场景 2：Prompt 升级内容验证
    # ================================================================
    assert "企业知识库专属问答助手" in SYSTEM_PROMPT_TEMPLATE
    assert "来源序号" in SYSTEM_PROMPT_TEMPLATE, "Prompt 应包含引用序号规范"
    assert "[1]" in SYSTEM_PROMPT_TEMPLATE, "Prompt 应给出引用标注示例"
    assert "礼貌拒绝" in SYSTEM_PROMPT_TEMPLATE, "Prompt 应包含无关问题拒绝规则"
    assert "先给结论" in SYSTEM_PROMPT_TEMPLATE, "Prompt 应约束结论先行的答案结构"
    assert "{context}" in SYSTEM_PROMPT_TEMPLATE, "Prompt 必须保留上下文占位符"
    print("[2] PROMPT OK: 引用序号 / 无关拒绝 / 结论先行 规则齐备")

    # ================================================================
    # 场景 3：新参数上传链路正常（切片参数生效）
    # ================================================================
    user_id, headers = _create_user(suffix)
    kb_id = _create_kb(user_id, suffix)
    txt_content = (
        "FastAPI 是一个现代的 Python Web 框架，支持自动文档生成。"
        "Qdrant 是一个高性能向量数据库，支持相似度检索。"
        "LangChain 提供了检索、问答等 RAG 核心能力的封装。"
    )
    files = {"file": (f"day10_{suffix}.txt", io.BytesIO(txt_content.encode("utf-8")), "text/plain")}
    resp = client.post(f"/api/v1/knowledge-bases/documents/upload/{kb_id}", files=files)
    assert resp.status_code == 201, f"上传失败: {resp.json()}"
    assert resp.json()["data"]["chunk_count"] >= 1
    print(f"[3] UPLOAD OK: 新切片参数下文档入库正常 chunks={resp.json()['data']['chunk_count']}")

    # ================================================================
    # 场景 4：检索优化确定性验证（合成数据：阈值过滤 + 去重）
    # ================================================================
    from core.langchain.qdrant_store import VectorSearchResult

    class _FakeRetriever:
        """返回合成检索结果，模拟重复切片与低相关切片。"""

        def __init__(self, results):
            self._results = results

        def search_with_score(self, query, *, knowledge_base_id=None, top_k=None):
            return self._results

        def health_check(self):
            return {"backend": "fake"}

    fake_results = [
        VectorSearchResult(page_content="FastAPI 是快速的 Web 框架。", metadata={}, score=0.5),
        VectorSearchResult(page_content="FastAPI 是快速的 Web 框架。", metadata={}, score=0.6),  # 重复切片
        VectorSearchResult(page_content="Qdrant 支持向量持久化。", metadata={}, score=0.9),
        VectorSearchResult(page_content="完全无关的噪声内容。", metadata={}, score=1.35),  # 低相关
    ]
    chain = StandardRAGChain(retriever=_FakeRetriever(fake_results), llm_client=None)
    filtered = chain._retrieve("FastAPI 是什么", knowledge_base_id=1, top_k=5)

    contents = [doc.page_content for doc in filtered]
    assert contents.count("FastAPI 是快速的 Web 框架。") == 1, "重复切片应被去重"
    assert "完全无关的噪声内容。" not in contents, "超过阈值 1.2 的低相关切片应被过滤"
    assert "Qdrant 支持向量持久化。" in contents, "阈值内的相关切片应保留"
    assert len(filtered) == 2, f"应剩余 2 条: {len(filtered)}"
    print("[4] FILTER+DEDUP OK: 低相关过滤与重复切片去重按预期工作")

    # 全部超阈值时应保留最优一条，避免误杀
    all_bad = [
        VectorSearchResult(page_content="噪声 A。", metadata={}, score=1.5),
        VectorSearchResult(page_content="噪声 B。", metadata={}, score=1.3),
    ]
    chain_bad = StandardRAGChain(retriever=_FakeRetriever(all_bad), llm_client=None)
    kept = chain_bad._retrieve("任意问题", knowledge_base_id=1, top_k=5)
    assert len(kept) == 1 and kept[0].page_content == "噪声 B。", "全超阈值时应保留最优一条"
    print("[4] KEEP-BEST OK: 全部超阈值时保留距离最小的一条")

    # ================================================================
    # 场景 5：优化前后对比实验（旧 500/50 vs 新 400/80）
    # 说明：离线 hash 嵌入按空白分词，英文语料才能体现词级语义区分，
    # 故对比实验使用英文语料；中文场景依赖真实嵌入模型时同样适用该调优方向。
    # ================================================================
    corpus_topics = {
        "fastapi": "FastAPI is a modern high performance Python web framework for building APIs "
        "with automatic OpenAPI documentation and dependency injection support.",
        "qdrant": "Qdrant is an open source high performance vector database with local persistence "
        "and metadata filtering for semantic retrieval in RAG systems.",
        "langchain": "LangChain is a framework for building LLM applications providing document "
        "loaders text splitters retrievers prompt templates and question answering chains.",
        "alembic": "Alembic is a database migration tool for SQLAlchemy supporting autogenerated "
        "revision scripts version upgrades and rollbacks.",
        "uv": "UV is a modern Python dependency manager replacing pip with lockfiles for "
        "reproducible environments and separated production development dependencies.",
    }
    corpus = " ".join(
        f"{text} {text}" for text in corpus_topics.values()
    )  # 重复一遍拉长语料，制造更多切片差异

    queries = [
        ("Which web framework generates OpenAPI documentation automatically?", "fastapi"),
        ("Which vector database supports metadata filtering?", "qdrant"),
        ("Which framework provides text splitters and retrievers?", "langchain"),
        ("Which tool supports database migration rollbacks?", "alembic"),
        ("Which dependency manager uses lockfiles to replace pip?", "uv"),
    ]

    tmp_root = Path(tempfile.mkdtemp(prefix="day10_compare_"))

    def _evaluate(chunk_size: int, chunk_overlap: int, tag: str) -> dict:
        """在独立临时向量库中评估一组切片参数的检索命中率。"""
        from core.langchain.qdrant_store import QdrantStoreManager

        store = QdrantStoreManager(collection_name=f"day10_{tag}", url=":memory:")
        splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        chunks = splitter.split_text(corpus)
        store.add_texts(texts=chunks, ids=[uuid4().hex for _ in chunks])

        hits, top1_hits, ranks = 0, 0, []
        for question, expected_topic in queries:
            expected_text = corpus_topics[expected_topic]
            docs = store.similarity_search_with_score(query=question, k=5)
            rank_of_hit = None
            for rank, (doc, _score) in enumerate(docs, start=1):
                if expected_text[:20] in doc.page_content:
                    rank_of_hit = rank
                    break
            if rank_of_hit is not None:
                hits += 1
                ranks.append(rank_of_hit)
                if rank_of_hit == 1:
                    top1_hits += 1
            else:
                ranks.append(6)  # 未命中按最差排名计

        return {
            "chunks": len(chunks),
            "hit_rate": hits / len(queries),
            "top1_rate": top1_hits / len(queries),
            "avg_rank": sum(ranks) / len(ranks),
        }

    try:
        old_metrics = _evaluate(500, 50, "old")
        new_metrics = _evaluate(400, 80, "new")
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    print("[5] COMPARE 旧参数 500/50: "
          f"chunks={old_metrics['chunks']} hit={old_metrics['hit_rate']:.0%} "
          f"top1={old_metrics['top1_rate']:.0%} avg_rank={old_metrics['avg_rank']:.2f}")
    print("[5] COMPARE 新参数 400/80: "
          f"chunks={new_metrics['chunks']} hit={new_metrics['hit_rate']:.0%} "
          f"top1={new_metrics['top1_rate']:.0%} avg_rank={new_metrics['avg_rank']:.2f}")

    assert new_metrics["hit_rate"] >= old_metrics["hit_rate"], (
        f"新参数命中率不应退化: new={new_metrics['hit_rate']} old={old_metrics['hit_rate']}"
    )
    assert new_metrics["avg_rank"] <= old_metrics["avg_rank"], (
        f"新参数平均排名不应退化: new={new_metrics['avg_rank']} old={old_metrics['avg_rank']}"
    )
    print("[5] COMPARE OK: 新参数命中率与平均排名不差于旧参数，调优方向成立")

    # ================================================================
    # 场景 6：问答链路在优化后仍端到端可用（LLM 不可用走兜底）
    # ================================================================
    ask_resp = client.post(
        "/api/v1/conversations/ask",
        headers=headers,
        json={"user_id": user_id, "knowledge_base_id": kb_id, "question": "FastAPI 是什么？"},
    )
    assert ask_resp.status_code == 200, f"问答接口应 200: {ask_resp.status_code}"
    ask_data = ask_resp.json()["data"]
    assert len(ask_data["answer"]) > 0
    print(f"[6] E2E OK: 优化后问答链路正常 success={ask_data['success']}")

    print("\n=== Day10 全部自检通过 ===")


if __name__ == "__main__":
    main()
