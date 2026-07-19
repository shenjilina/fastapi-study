"""Chroma 向量库数据查看工具。

用法：uv run python scripts/chroma_viewer.py
"""

from __future__ import annotations

from core.langchain.chroma_store import ChromaStoreManager


def view_all_data() -> None:
    """打印当前 Chroma collection 中的全部数据。"""
    store = ChromaStoreManager(collection_name="rag_documents")

    # 1. 健康状态
    health = store.health_check()
    print("=" * 60)
    print("向量库状态")
    print("=" * 60)
    for key, value in health.items():
        print(f"  {key}: {value}")

    if health["count"] == 0:
        print("\n当前 collection 为空，没有向量数据。")
        return

    # 2. 查询全部数据（不返回向量本身，只看元数据和文本）
    result = store._store.get(include=["metadatas", "documents"])
    ids = result.get("ids", [])
    documents = result.get("documents", [])
    metadatas = result.get("metadatas", [])

    print(f"\n共 {len(ids)} 条记录：")
    print("-" * 60)
    for i, (doc_id, doc_text, meta) in enumerate(
        zip(ids, documents, metadatas), start=1
    ):
        preview = doc_text[:120] + "..." if len(doc_text) > 120 else doc_text
        print(f"\n[{i}] id={doc_id}")
        print(f"    metadata={meta}")
        print(f"    content={preview}")

    # 3. 按知识库分组统计
    print("\n" + "=" * 60)
    print("按知识库分组统计")
    print("=" * 60)
    kb_counts: dict[int, int] = {}
    for meta in metadatas:
        if meta and "knowledge_base_id" in meta:
            kb_id = meta["knowledge_base_id"]
            kb_counts[kb_id] = kb_counts.get(kb_id, 0) + 1
    for kb_id, count in sorted(kb_counts.items()):
        print(f"  知识库 {kb_id}: {count} 条向量")

    # 4. 按文档分组统计
    print("\n按文档分组统计")
    print("-" * 60)
    doc_counts: dict[int, int] = {}
    doc_filenames: dict[int, str] = {}
    for meta in metadatas:
        if meta and "document_id" in meta:
            doc_id = meta["document_id"]
            doc_counts[doc_id] = doc_counts.get(doc_id, 0) + 1
            if "filename" in meta:
                doc_filenames[doc_id] = meta["filename"]
    for doc_id, count in sorted(doc_counts.items()):
        filename = doc_filenames.get(doc_id, "unknown")
        print(f"  文档 {doc_id} ({filename}): {count} 条向量")


if __name__ == "__main__":
    view_all_data()
