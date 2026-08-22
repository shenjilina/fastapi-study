"""Remove vectors belonging to pre-files documents before schema migration."""

import sqlite3

from core.langchain.chroma_store import get_chroma_store


def main() -> None:
    connection = sqlite3.connect("rag_project.db")
    try:
        document_ids = [row[0] for row in connection.execute("SELECT id FROM documents WHERE file_id IS NULL")]
    finally:
        connection.close()

    store = get_chroma_store()
    for document_id in document_ids:
        store.delete_by_metadata({"document_id": document_id})
    print(f"Cleaned vectors for {len(document_ids)} legacy documents")


if __name__ == "__main__":
    main()
