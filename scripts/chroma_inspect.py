"""快速查看 chroma.sqlite3 中的 collection 列表。"""

import sqlite3

conn = sqlite3.connect(r"chroma/chroma.sqlite3")
cursor = conn.cursor()

# 查看所有表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cursor.fetchall()]
print("Tables:", tables)

# 查看所有 collection
cursor.execute("SELECT id, name, dimension FROM collections")
rows = cursor.fetchall()
print(f"\nCollections ({len(rows)}):")
for r in rows:
    print(f"  id={r[0]}  name={r[1]}  dim={r[2]}")

# 查看每个 collection 中的数据量
cursor.execute("SELECT collection_id, COUNT(*) FROM embeddings GROUP BY collection_id")
emb_rows = cursor.fetchall()
if emb_rows:
    print("\nEmbeddings per collection:")
    for r in emb_rows:
        print(f"  collection_id={r[0]}  count={r[1]}")
else:
    print("\nNo embeddings data found.")

# 查看嵌入片段内容（取前5条）
cursor.execute("SELECT id, collection_id, document, metadata FROM embeddings LIMIT 5")
doc_rows = cursor.fetchall()
if doc_rows:
    print("\nSample documents (first 5):")
    for r in doc_rows:
        doc_preview = (r[2] or "")[:80]
        print(f"  id={r[0]}  collection={r[1]}  doc={doc_preview}...")

conn.close()
