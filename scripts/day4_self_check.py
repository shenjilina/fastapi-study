"""Day4 向量能力自检脚本。"""

from uuid import uuid4

from core.langchain.chroma_store import ChromaStoreManager
from core.langchain.embedding import get_embedding_client


def main() -> None:
    """验证嵌入单例、文本入库、向量检索和删除功能。"""
    collection_name = f"day4_check_{uuid4().hex[:8]}"
    chroma_store = ChromaStoreManager(collection_name=collection_name)
    embedding_client = get_embedding_client()

    print("EMBEDDING BACKEND:", embedding_client.get_backend_summary())

    texts = [
        "FastAPI is a high performance Python web framework.",
        "Chroma can persist vector embeddings locally.",
        "LangChain helps organize retrieval and question answering workflows.",
    ]
    metadatas = [
        {"topic": "fastapi", "group": "day4"},
        {"topic": "chroma", "group": "day4"},
        {"topic": "langchain", "group": "day4"},
    ]

    inserted_ids = chroma_store.add_texts(texts, metadatas=metadatas)
    print("INSERTED IDS:", inserted_ids)
    print("COUNT AFTER INSERT:", chroma_store.count())

    search_results = chroma_store.similarity_search(
        "Which tool persists vectors locally?",
        k=2,
        metadata_filter={"group": "day4"},
    )
    print("SEARCH RESULTS:", [item.metadata for item in search_results])

    deleted_count = chroma_store.delete_by_metadata({"topic": "chroma"})
    print("DELETED COUNT:", deleted_count)
    print("COUNT AFTER DELETE:", chroma_store.count())

    cleanup_count = chroma_store.clear_collection()
    print("CLEANUP COUNT:", cleanup_count)
    print("FINAL HEALTH:", chroma_store.health_check())


if __name__ == "__main__":
    main()
