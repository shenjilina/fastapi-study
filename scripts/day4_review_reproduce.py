"""Day4 复习独立复现：不引用项目已有封装，从零实现嵌入 + 向量库核心流程。

复现目标：
1. 实现 Embeddings 接口的离线嵌入
2. 直接使用 Chroma 完成增删查
3. 验证持久化、metadata 过滤、批量删除
"""

from __future__ import annotations

import math
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings


class SimpleHashEmbeddings(Embeddings):
    """独立实现的离线嵌入：SHA256 分词 + L2 归一化。"""

    def __init__(self, dim: int = 32) -> None:
        self.dim = dim

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in text.strip().lower().split():
            digest = sha256(token.encode("utf-8")).digest()
            for i in range(self.dim):
                vec[i] += (digest[i % len(digest)] / 255.0) - 0.5
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec] if norm > 0 else vec

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def build_store(collection: str, persist_dir: str, embedding: Embeddings) -> Chroma:
    """创建持久化 Chroma 实例。"""
    Path(persist_dir).mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=collection,
        persist_directory=persist_dir,
        embedding_function=embedding,
    )


def main() -> None:
    """独立复现完整流程：建库 -> 入库 -> 检索 -> 删除 -> 统计。"""
    persist_dir = "./chroma_review"
    collection = f"review_{uuid4().hex[:8]}"
    embedding = SimpleHashEmbeddings(dim=32)

    store = build_store(collection, persist_dir, embedding)

    # --- 增 ---
    texts = ["FastAPI 很快", "Chroma 存向量", "LangChain 做 RAG"]
    metadatas = [{"tag": "web"}, {"tag": "vector"}, {"tag": "rag"}]
    ids = [uuid4().hex for _ in texts]
    store.add_texts(texts=texts, metadatas=metadatas, ids=ids)
    print(f"入库 {len(ids)} 条")

    # --- 查 ---
    results = store.similarity_search("什么工具存向量", k=2)
    print(f"检索到 {len(results)} 条:")
    for doc in results:
        print(f"  content={doc.page_content}, metadata={doc.metadata}")

    # 带 score 的检索（score 是距离，越小越相似）
    scored = store.similarity_search_with_score("什么工具存向量", k=2)
    print("带分数检索:")
    for doc, score in scored:
        print(f"  distance={score:.4f}, content={doc.page_content}")

    # --- 删 ---
    store.delete(ids=[ids[0]])
    remaining = store.get(include=[])
    print(f"删除 1 条后剩余 {len(remaining['ids'])} 条")

    # 按 metadata 删除
    to_delete = store.get(where={"tag": "rag"}, include=[])
    if to_delete["ids"]:
        store.delete(ids=to_delete["ids"])
        print(f"按 metadata 删除 {len(to_delete['ids'])} 条")

    final = store.get(include=[])
    print(f"最终剩余 {len(final['ids'])} 条")


if __name__ == "__main__":
    main()
