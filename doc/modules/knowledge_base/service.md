# `service.py` (knowledge_base) 文档

此文件是知识库模块的核心，实现了RAG（检索增强生成）的完整流程，包括文档的摄入（Ingest）和检索（Retrieval）。它整合了文本提取、分割、向量化、存储、混合检索、重排序和多样性选择等多个复杂步骤。

## 核心组件与模型

- **嵌入模型 (`_model`)**: 使用 `sentence-transformers` 库加载一个预训练的嵌入模型（如 `intfloat/multilingual-e5-base`）。这个模型负责将文本转换为能够表示其语义的向量。
- **重排序模型 (`_reranker_instance`)**: 使用 `sentence-transformers` 的 `CrossEncoder` 加载一个重排序模型（如 `BAAI/bge-reranker-base`）。它用于对初步检索到的结果进行更精细的相关度打分，提高最终结果的质量。
- **`RetrievedChunk` (Dataclass)**: 一个数据类，用于在检索过程中封装每个候选区块的丰富信息，包括原始chunk对象、各种得分（向量相似度、BM25、重排序、MMR）、来源等，便于调试和融合。
- **`RagSearchConfig` (Dataclass)**: 一个配置类，用于在每次搜索时，从动态配置服务中聚合所有与RAG相关的参数，如 `top_k`, `rerank_enabled`, `bm25_weight` 等。

## 文档摄入 (Ingest) 流程

这是将外部文档转换为知识库内部可检索格式的过程。

### `ingest_document_file(...)` / `ingest_document_content(...)`
- **功能**: 分别处理从上传文件和直接文本内容进行的文档摄入。
- **核心流程 (`_persist_chunks`)**:
    1.  **提取 (Extract)**: 调用 `extract_from_bytes` 或 `extract_from_text`，使用 `unstructured.io` 库从原始文件（PDF, DOCX, HTML等）或文本中提取出结构化的元素（如标题、段落、列表项）。
    2.  **分割 (Split)**: 调用 `split_elements`，将提取出的元素分割成大小适中的、语义相对完整的文本区块（Chunks）。分割策略会考虑文本类型（如代码、普通文本）和动态配置中的参数。
    3.  **向量化 (Vectorize)**: 将所有文本区块批量送入嵌入模型 (`_model.encode`)，生成它们的语义向量。
    4.  **持久化 (Persist)**: 调用 `crud_knowledge_base.bulk_create_document_chunks`，将区块的文本内容、向量、语言、全文检索向量等信息批量存入数据库。

## 检索 (Retrieval) 流程

这是RAG的核心，即根据用户查询，从知识库中找出最相关的知识区块。

### `search_similar_chunks(db, query, top_k, ...)`
- **功能**: 实现一个复杂的、多阶段的混合检索流程。
- **流程详解**:
    1.  **配置加载**: 调用 `_build_rag_config` 从动态配置服务中加载所有RAG相关参数。
    2.  **查询处理**: 对用户查询 `query` 进行语言检测和向量化。
    3.  **初步召回 (Candidate Generation)**:
        - **向量召回**: 调用 `crud_knowledge_base.fetch_chunk_candidates_by_embedding`，使用向量余弦距离，从数据库中召回大量（`oversample`）初步候选的区块。
        - **BM25召回与融合 (Hybrid Search)**: 如果启用了BM25，调用 `_apply_bm25_fusion`：
            - 执行全文检索（BM25）召回另一组候选区块。
            - 将向量召回和BM25召回的结果合并。
            - 对于同时被两种方式召回的区块，使用一个加权公式 (`bm25_weight`) 来融合它们的向量相似度得分和BM25得分，计算出一个新的 `coarse_score`（粗排分）。
    4.  **过滤与粗排**: 
        - 根据 `min_sim` 阈值过滤掉相似度过低的候选者。
        - 根据 `coarse_score` 对所有候选者进行初步排序。
    5.  **重排序 (Re-ranking)**:
        - 如果启用了重排序 (`rerank_enabled`)，取粗排分最高的N个候选者（`rerank_candidates`）。
        - 将这些候选者的文本内容与用户查询一起送入 `CrossEncoder` 重排序模型，得到更精确的相关度得分 (`rerank_score`)。
        - 将 `rerank_score` 与 `coarse_score` 结合，计算出新的、更准确的 `score`。
    6.  **多样性选择 (MMR - Maximal Marginal Relevance)**:
        - 调用 `_mmr_select` 对重排后的结果进行处理。
        - MMR算法在保证相关性的同时，会惩罚那些与已选结果内容相似的候选者，从而提高最终结果的多样性，避免内容冗余。
        - 它会迭代地选择下一个区块，使得该区块与查询的相关性 (`score`) 尽可能高，同时与已选区块的相似度 (`redundancy`) 尽可能低。
    7.  **最终排序与返回**: 将经过MMR选择后的 `top_k` 个结果，按最终的 `mmr_score` 或 `score` 排序后返回。

## 总结

这个服务实现了一个业界领先的RAG检索流程。它不仅仅是简单的向量搜索，而是融合了关键词搜索（BM25）、精细化重排序（Cross-Encoder）和最大边缘相关性（MMR）等多种技术，并通过动态配置系统实现了高度的灵活性和可调控性，以适应不同的应用场景和性能要求。
