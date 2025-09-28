# `models.py` (knowledge_base) 文档

此文件定义了与知识库功能相关的SQLAlchemy ORM模型，是RAG（检索增强生成）功能的数据基础。它主要包含 `KnowledgeDocument`（知识文档）和 `KnowledgeChunk`（知识区块）两个模型。

## `KnowledgeDocument(Base)` 模型

这个类代表了一个被纳入知识库的原始文档，映射到 `knowledge_documents` 表。一个文档可以是一个上传的文件、一个网页、或通过API接入的一段文本。

### 主要字段
- **`id: Mapped[int]`**: 主键，自增整数。
- **`source_type: Mapped[Optional[str]]`**: 文档的来源类型，例如 `"upload"`, `"url"`, `"api"`。
- **`source_ref: Mapped[Optional[str]]`**: 文档的来源引用。根据 `source_type` 的不同，这里可以存储文件的路径、网页的URL或外部系统的ID等。
- **`title: Mapped[Optional[str]]`**: 文档的标题。
- **`language: Mapped[Optional[str]]`**: 文档的主要语言（例如 `"en"`, `"zh"`）。
- **`mime: Mapped[Optional[str]]`**: 文档的MIME类型（例如 `"text/plain"`, `"application/pdf"`）。
- **`checksum: Mapped[Optional[str]]`**: 文档内容的校验和（如MD5或SHA256），用于检测重复文档。
- **`meta: Mapped[Dict | None]`**: 一个JSONB字段，用于存储与文档相关的任意元数据。
- **`tags: Mapped[List[str] | None]`**: 一个JSONB字段，用于存储文档的标签列表，方便分类和过滤。
- **`created_by: Mapped[Optional[str]]`**: 创建该文档的用户或系统的标识。
- **`created_at: Mapped[datetime]`**: 记录的创建时间。

### 关联关系
- **`chunks: Mapped[List["KnowledgeChunk"]]`**: 定义了与 `KnowledgeChunk` 模型的一对多关系。当一个 `KnowledgeDocument` 被删除时，所有与之关联的 `KnowledgeChunk` 记录也会被级联删除 (`cascade="all, delete-orphan"`)。

## `KnowledgeChunk(Base)` 模型

这个类是RAG功能的核心。它代表了从原始文档中分割出来的一个个文本区块（Chunk），映射到 `knowledge_chunks` 表。将文档分割成小的、语义完整的区块是进行向量检索的基础。

### 主要字段
- **`id: Mapped[int]`**: 主键，自增整数。
- **`document_id: Mapped[Optional[int]]`**: 外键，关联到 `knowledge_documents` 表，指明该区块属于哪个原始文档。设置了 `ondelete="CASCADE"`，确保在文档被删除时，数据库层面会自动删除其下的所有区块。
- **`chunk_index: Mapped[Optional[int]]`**: 该区块在原始文档中的顺序索引。
- **`content: Mapped[str]`**: 区块的纯文本内容。
- **`embedding: Mapped[List[float]]`**: **核心字段**。这是一个向量（Vector）类型，由 `pgvector` 扩展提供。它存储了 `content` 文本经过嵌入模型（Embedding Model）计算后得到的语义向量。这个向量是实现语义搜索的关键。
    - `Vector(dim=768)`: 声明了向量的维度为768，这个值必须与所使用的嵌入模型的输出维度严格一致。
- **`language: Mapped[Optional[str]]`**: 区块的语言或类型（例如，对于代码文件，这里可以标记为 `"python"`）。
- **`search_vector: Mapped[Optional[str]]`**: 这是一个 `TSVECTOR` 类型，由PostgreSQL的全文检索引擎使用。它存储了 `content` 文本经过分词和词干提取后生成的全文检索向量，用于支持传统的关键词搜索。
- **`created_at: Mapped[datetime]`**: 记录的创建时间。

### 关联关系
- **`document: Mapped[Optional[KnowledgeDocument]]`**: 定义了与 `KnowledgeDocument` 模型的多对一关系，方便从区块对象直接访问其所属的文档对象。
