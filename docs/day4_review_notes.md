# Day4 复习笔记：Embedding + Chroma 向量库

## 一、知识脉络清单

### 1. 嵌入模型（Embedding）

**核心概念**：把文本转成定长浮点向量，让语义相近的文本在向量空间中距离更近。

**实现层次**：
- `Embeddings`（langchain_core 抽象基类）：定义 `embed_documents` 和 `embed_query` 两个接口
- `HashFallbackEmbeddings`：离线兜底，SHA256 分词 -> 逐维累加 -> L2 归一化
- `SentenceTransformerEmbeddings`：真实模型，`local_files_only=True` 避免联网下载
- `ResilientEmbeddingClient`：外观模式，先检测本地模型路径是否存在，不存在则回退

**关键语法**：
- `@lru_cache` 装饰器：保证 `get_embedding_client()` 全局只初始化一次
- `Path(model_name).exists()`：判断配置的模型名是否是本地目录
- `from __future__ import annotations`：延迟类型注解求值，允许前向引用

### 2. Chroma 向量库

**核心概念**：本地持久化的向量数据库，支持相似度检索和 metadata 过滤。

**封装能力**：
- 增：`add_texts(texts, metadatas, ids)` -> 返回 ID 列表
- 查：`similarity_search(query, k, filter)` -> 返回 Document 列表
- 查（带分数）：`similarity_search_with_score` -> 返回 (Document, distance) 元组
- 删：`delete_by_ids(ids)` / `delete_by_metadata(filter)` / `clear_collection()`
- 统计：`count()` / `health_check()`

**异常恢复**：
- `_initialize_store` 先尝试正常建库
- 失败后 `_backup_broken_store` 把损坏目录移到备份路径
- 再重建一个全新的 Chroma 实例
- 二次失败才抛 `ChromaStoreInitializationError`

### 3. 数据结构

- `VectorSearchResult`（dataclass + slots）：统一检索返回结构，包含 page_content / metadata / score
- `@dataclass(slots=True)`：Python 3.10+ 优化，减少内存占用

---

## 二、逐行复盘发现的问题与修正

### 问题 1：k 参数缺少校验
- **位置**：`chroma_store.py` similarity_search / similarity_search_with_score
- **问题**：传 `k=0` 或负数会让 Chroma 内部报错，且错误信息不直观
- **修正**：在方法入口加 `if k <= 0: raise ChromaStoreOperationError("k 必须大于 0")`

### 问题 2：ids 长度未校验
- **位置**：`chroma_store.py` add_texts
- **问题**：调用方传入的 `ids` 列表长度可能与 `texts` 不一致，导致 Chroma 内部报错
- **修正**：增加 `if len(document_ids) != len(texts)` 校验

### 问题 3：备份路径时间戳冲突
- **位置**：`chroma_store.py` _backup_broken_store
- **问题**：同一秒内重复调用，备份目录名相同，`shutil.move` 会失败
- **修正**：路径后缀追加 `uuid4().hex[:6]` 随机串

### 问题 4：score 语义不明确
- **位置**：`chroma_store.py` similarity_search_with_score
- **问题**：Chroma 返回的是距离值（越小越相似），但字段名叫 score，容易误解为相似度分数
- **修正**：在 docstring 中明确标注 "score 是距离值，越小表示越相似"

### 问题 5：_collection 私有属性访问无说明
- **位置**：`chroma_store.py` _initialize_store / count
- **问题**：`store._collection.count()` 访问了私有属性，但没说明原因
- **修正**：添加注释说明这是 LangChain Chroma 集成中获取 count 的标准方式

### 问题 6：嵌入空输入未处理
- **位置**：`embedding.py` HashFallbackEmbeddings
- **问题**：传入空字符串或空列表时没有提前返回，虽然不会崩溃但行为不够明确
- **修正**：空列表返回 `[]`，空字符串返回零向量

---

## 三、独立复现验证

复现脚本：`scripts/day4_review_reproduce.py`

不引用项目已有封装，从零实现：
1. `SimpleHashEmbeddings`：独立实现 Embeddings 接口
2. `build_store`：直接创建 Chroma 实例
3. 完整流程：入库 3 条 -> 检索 2 条 -> 带分数检索 -> 按 ID 删除 -> 按 metadata 删除

**复现结果**：
```
入库 3 条
检索到 2 条:
  content=Chroma 存向量, metadata={'tag': 'vector'}
  content=LangChain 做 RAG, metadata={'tag': 'rag'}
带分数检索:
  distance=1.5717, content=Chroma 存向量
  distance=2.1239, content=LangChain 做 RAG
删除 1 条后剩余 2 条
按 metadata 删除 1 条
最终剩余 1 条
```

---

## 四、重难点与避坑要点

### 难点 1：嵌入模型的本地可用性
**问题**：`sentence-transformers` 需要下载模型，离线环境会卡住或超时。
**解决方案**：默认使用 `local_files_only=True`，并在模型路径不存在时回退到 hash 嵌入。
**避坑**：不要在生产环境直接用 hash 嵌入，它只是保证"代码能跑"，检索质量很低。

### 难点 2：Chroma 持久化目录损坏
**问题**：异常退出后目录可能残留锁文件或损坏数据，导致下次启动失败。
**解决方案**：初始化时主动访问 collection 触发异常，失败后把旧目录移走再重建。
**避坑**：`shutil.move` 在 Windows 上如果目录被占用会失败，异常恢复的二次失败需要向上抛。

### 难点 3：LangChain Chroma 的私有 API
**问题**：获取 collection 内文档数量只能用 `store._collection.count()`，这是私有属性。
**避坑**：LangChain Chroma 集成没有暴露公开的 count 方法，只能这样用。如果后续升级 LangChain 版本，这里可能会变。

### 难点 4：metadata 过滤语法
**问题**：Chroma 的 `filter` 参数只支持精确匹配（`{"key": "value"}`），不支持范围查询。
**避坑**：如果需要范围查询或复杂条件，需要在业务层先查出 ID 再删除，不能指望 Chroma 的 filter。

### 难点 5：score 是距离不是相似度
**问题**：`similarity_search_with_score` 返回的值越小越相似，和直觉相反。
**避坑**：在业务层如果需要"相似度分数"展示给用户，需要做 `1 / (1 + distance)` 之类的转换。

---

## 五、仍存疑惑的问题清单

1. **LangChain Chroma 的持久化机制**：`persist_directory` 在 ChromaDB 1.x 版本中是否自动持久化？还是需要手动调用 `persist()`？当前代码没有显式调用 `persist()`，但数据似乎已经持久化了。

2. **Chroma collection 的生命周期**：同一个 `persist_directory` 下可以有多个 collection，删除 collection 的正确方式是什么？当前用 `delete(ids=...)` 清空数据，但 collection 本身还在。

3. `sentence-transformers` 的 `local_files_only=True` 和 `model_kwargs` 的关系：如果后续需要在线下载模型，应该改这个参数还是用 `cache_folder` 指定缓存目录？

4. **Chroma 的并发安全**：多个请求同时写入同一个 collection 会不会有锁竞争？当前用了 `@lru_cache` 单例，但 Chroma 本身的并发能力如何？

5. **LangChain Embeddings 接口的 `embed_documents` 和 `embed_query` 区别**：为什么分成两个方法？在 `SentenceTransformer` 里它们调用的是同一个 `model.encode`，只是输入维度不同。这是设计冗余还是有意为之？
