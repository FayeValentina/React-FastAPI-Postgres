# `knowledge.py` (endpoints) 文档

此文件定义了与知识库管理和检索功能相关的所有API端点。这些端点是RAG（检索增强生成）功能的后端基础，提供了文档和知识区块的完整生命周期管理以及核心的搜索功能。

## Router 配置
- **`prefix`**: `/knowledge`
- **`tags`**: `["knowledge"]`

## 文档管理 Endpoints

### `POST /documents`
- **功能**: 创建一个新的知识文档记录（元数据）。
- **请求体**: `KnowledgeDocumentCreate`。
- **响应模型**: `KnowledgeDocumentRead`。
- **逻辑**: 调用 `crud_knowledge_base.create_document` 在数据库中创建一个文档条目，此时该条目尚不包含任何内容区块。

### `POST /documents/{document_id}/ingest`
- **功能**: 将纯文本内容“摄入”到一个已存在的文档中。
- **请求体**: `KnowledgeDocumentIngestRequest` (包含 `content` 和 `overwrite` 标志)。
- **逻辑**: 调用 `knowledge_base_service.ingest_document_content`，该服务会处理文本的分割、向量化，并将生成的区块存入数据库。

### `POST /documents/{document_id}/ingest/upload`
- **功能**: 通过文件上传的方式，将文档内容“摄入”到一个已存在的文档中。
- **请求体**: `multipart/form-data`，包含 `file` 和 `overwrite` 字段。
- **逻辑**: 调用 `knowledge_base_service.ingest_document_file`，该服务会处理文件的解析、文本提取、分割、向量化和存储。

### `GET /documents`
- **功能**: 分页列出所有已创建的知识文档。
- **响应模型**: `list[KnowledgeDocumentRead]`。

### `GET /documents/{document_id}`
- **功能**: 获取单个知识文档的元数据。
- **响应模型**: `KnowledgeDocumentRead`。

### `PATCH /documents/{document_id}`
- **功能**: 更新单个知识文档的元数据（如标题、标签等）。
- **请求体**: `KnowledgeDocumentUpdate`。
- **响应模型**: `KnowledgeDocumentRead`。

### `DELETE /documents/{document_id}`
- **功能**: 删除一个知识文档及其所有关联的知识区块。
- **逻辑**: 调用 `crud_knowledge_base.delete_document`，利用数据库的级联删除功能完成操作。

## 区块管理 Endpoints

### `GET /documents/{document_id}/chunks`
- **功能**: 列出某个特定文档下的所有知识区块。
- **响应模型**: `list[KnowledgeChunkRead]`。

### `PATCH /chunks/{chunk_id}`
- **功能**: 更新单个知识区块的文本内容或块序。
- **请求体**: `KnowledgeChunkUpdate`（仅 `content` 与 `chunk_index` 字段）。
- **逻辑**: 调用 `knowledge_base_service.update_chunk`。当 `content` 发生变化时会自动重算嵌入、语言及全文检索向量。

### `DELETE /chunks/{chunk_id}`
- **功能**: 删除单个知识区块。

## 搜索 Endpoint

### `POST /search`
- **功能**: 在知识库中执行搜索。
- **请求体**: `KnowledgeSearchRequest` (包含 `query` 和 `top_k`)。
- **响应模型**: `list[KnowledgeSearchResult]`。
- **逻辑**: 
    - **注意**: 此端点的当前实现**仅使用了BM25（关键词）搜索**，并未完全实现 `service.py` 中定义的包含向量搜索、重排序和MMR的完整混合检索流程。
    - 它调用 `fetch_bm25_matches` 从数据库中获取与查询相关的区块，并根据BM25得分进行排序。
    - 将结果格式化为 `KnowledgeSearchResult` 列表并返回。
