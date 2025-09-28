# `schemas.py` (knowledge_base) 文档

此文件定义了与知识库功能相关的Pydantic模型，用于API接口的数据验证、请求体结构定义和响应体序列化。

## 文档 (Document) 相关模型

### `KnowledgeDocumentBase`
- **用途**: 定义了知识文档的通用基础字段，如 `source_type`, `source_ref`, `title`, `language` 等。其他文档模型继承自它以复用字段定义。

### `KnowledgeDocumentCreate`
- **用途**: 作为创建新知识文档API的请求体模型。它直接继承自 `KnowledgeDocumentBase`，包含了创建一个新文档所需的所有信息。

### `KnowledgeDocumentRead`
- **用途**: 作为API响应返回给客户端的文档信息模型。
- **字段**: 继承自 `KnowledgeDocumentBase`，并增加了数据库生成的 `id` 和 `created_at` 字段。
- **配置**: 设置了 `model_config = {"from_attributes": True}`，允许直接从 `KnowledgeDocument` ORM实例进行转换。

### `KnowledgeDocumentIngestRequest`
- **用途**: 作为文档“摄入”（Ingest）API的请求体模型。这个API负责接收原始文本内容，并将其处理（分割、向量化）后存入知识库。
- **字段**:
    - `content: str`: 需要被处理的完整文本内容。
    - `overwrite: bool`: 一个布尔标志，如果为 `True`，则在摄入新内容前会先删除该文档下所有已存在的旧区块。

### `KnowledgeIngestResult`
- **用途**: 文档摄入成功后的响应模型。
- **字段**:
    - `document_id: int`: 被操作的文档ID。
    - `chunks: int`: 本次操作成功创建的区块数量。

### `KnowledgeDocumentUpdate`
- **用途**: 用于更新文档元数据的请求体模型。所有字段都是可选的，支持部分更新。

## 区块 (Chunk) 相关模型

### `KnowledgeChunkRead`
- **用途**: 作为API响应返回给客户端的单个知识区块的信息模型。
- **字段**: 包含了区块的核心信息，如 `id`, `document_id`, `content`, `language` 等。
- **配置**: 同样设置了 `from_attributes=True` 以便从ORM实例转换。

### `KnowledgeChunkUpdate`
- **用途**: 用于更新单个知识区块内容的请求体模型。所有字段都是可选的。

## 检索 (Search) 相关模型

### `KnowledgeSearchRequest`
- **用途**: 作为知识库搜索API的请求体模型。
- **字段**:
    - `query: str`: 用户的查询语句，不能为空。
    - `top_k: int`: 希望返回的最相关结果的数量，被限制在1到50之间。

### `KnowledgeSearchResult`
- **用途**: 作为知识库搜索API的响应体中，列表里的单个结果项的模型。
- **字段**: 这是一个信息非常丰富的模型，旨在提供充分的上下文和可调试性。
    - `id`, `document_id`, `content`, ...: 区块本身的基本信息。
    - `score: float`: **综合得分**。这是由RAG服务融合了多种召回策略（如向量相似度、BM25得分）后计算出的最终相关度得分。
    - `similarity: float`: **向量相似度**。仅表示该区块与查询语句在语义向量空间中的相似度（通常是余弦相似度的归一化结果）。
    - `bm25_score: Optional[float]`: **BM25得分**。如果该区块是通过关键词搜索（BM25）召回的，这里会包含其原始的BM25分数。
    - `retrieval_source: str`: **召回来源**。明确指出该区块是通过哪种方式被检索到的，例如 `"vector"`（向量搜索）、`"bm25"`（关键词搜索）或 `"hybrid"`（混合模式）。
