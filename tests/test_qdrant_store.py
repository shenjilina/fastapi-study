from core.langchain.qdrant_store import QdrantStoreManager


def test_qdrant_store_supports_write_filter_search_and_delete() -> None:
    store = QdrantStoreManager(
        collection_name="test_rag_documents",
        url=":memory:",
    )

    ids = store.add_texts(
        ["FastAPI is a web framework", "Qdrant stores vectors"],
        metadatas=[{"knowledge_base_id": 1}, {"knowledge_base_id": 2}],
        ids=["doc-1", "doc-2"],
    )

    assert ids == ["doc-1", "doc-2"]
    assert store.count() == 2
    results = store.similarity_search("web framework", k=2, metadata_filter={"knowledge_base_id": 1})
    assert len(results) == 1
    assert results[0].metadata["knowledge_base_id"] == 1

    assert store.delete_by_metadata({"knowledge_base_id": 1}) == 1
    assert store.count() == 1
    store.delete_by_ids(["doc-2"])
    assert store.count() == 0
