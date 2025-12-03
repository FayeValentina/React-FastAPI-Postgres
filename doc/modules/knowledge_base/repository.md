# `repository.py` (knowledge_base) 文档

此文件定义了 `CRUDKnowledgeBase` 类，它是一个仓库（Repository），封装了所有与知识库相关的数据库操作，包括对 `KnowledgeDocument`（文档）和 `KnowledgeChunk`（区块）的增删改查，以及核心的向量检索和全文检索功能。

## `CRUDKnowledgeBase` 类

### 文档 (Document) 相关方法

- **`create_document(db, data)`**: 创建一个新的知识文档记录，但不立即提交事务，而是执行 `flush`。这允许在同一个事务中继续创建与该文档关联的区块。
- **`delete_document(db, document_id)`**: 根据ID删除一个文档。由于在模型中设置了级联删除，所有属于该文档的区块也会被自动删除。
- **`get_all_documents(db, ...)`**: 分页获取所有文档的列表。
- **`get_document_by_id(db, document_id)`**: 获取单个文档的详细信息。
- **`update_document_metadata(db, document_id, updates)`**: 更新文档的元数据，如标题、标签等。

### 区块 (Chunk) 相关方法

- **`get_chunks_by_document_id(db, document_id)`**: 获取某个特定文档下的所有区块。
- **`delete_chunks_by_document_id(db, document_id, ...)`**: 删除某个特定文档下的所有区块。
- **`bulk_create_document_chunks(db, document_id, chunks, ...)`**: **核心方法之一**。用于批量地为一个文档创建多个知识区块。
    - **流程**: 
        1.  遍历传入的 `chunks` 数据（每个chunk包含索引、内容、嵌入向量等）。
        2.  对于每个区块，调用 `tokenize_for_search` 生成用于全文检索的文本。
        3.  使用 `func.to_tsvector` 将其转换为数据库的 `TSVECTOR` 格式。
        4.  将 `embedding` 向量（`np.asarray`）和所有其他信息一起创建一个 `KnowledgeChunk` 对象，并添加到数据库会话中。
    - **性能**: 通过批量添加和单次提交（或 `flush`），显著提高了数据入库的效率。
- **`delete_chunk(db, chunk)`**: 删除单个区块。

### 检索 (Retrieval) 方法

这是实现RAG功能的关键所在。

- **`search_by_vector(db, query_embedding, limit)`**: **语义搜索**。
    - **功能**: 根据用户问题的嵌入向量 `query_embedding`，在 `knowledge_chunks` 表中查找语义最相似的区块。
    - **实现**: 
        1.  使用 `pgvector` 提供的 `<=>` 操作符（在SQLAlchemy中表现为 `cosine_distance` 方法）来计算查询向量与数据库中每个区块向量之间的余弦距离。
        2.  按距离升序排序（距离越小越相似）。
        3.  返回距离最近的 `limit` 个区块及其与查询的距离。
        4.  使用 `selectinload` 预加载关联的 `document` 对象，避免N+1查询问题。

- **`search_by_bm25(db, query, limit, ...)`**: **关键词搜索 (BM25)**。
    - **功能**: 使用传统的全文检索技术（BM25算法的变体）来根据关键词 `query` 查找相关的区块。
    - **实现**: 
        1.  调用 `tokenize_for_search` 对查询语句进行分词和标准化。
        2.  使用 `func.plainto_tsquery` 将其转换为数据库的 `tsquery` 格式。
        3.  使用 `@@` 操作符（PostgreSQL全文检索的匹配操作符）来筛选出 `search_vector` 字段与查询匹配的区块。
        4.  使用 `func.ts_rank_cd` 计算每个匹配区块与查询的相关度得分。
        5.  按相关度得分降序排序并返回结果。

## 全局实例
- `crud_knowledge_base = CRUDKnowledgeBase()`: 创建了一个全局唯一的仓库实例，供上层服务调用。
