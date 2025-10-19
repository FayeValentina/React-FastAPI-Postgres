# `service.py` (knowledge_base) 文档

`service.py` 现在只作为知识库子系统的门面（facade），导出下列模块的公共 API：

- `config`：动态配置解析（`resolve_dynamic_settings`, `build_rag_config`, `RagSearchConfig`）。
- `embeddings`：惰性加载的向量化/重排序模型工厂。
- `ingestion`：文档提取、切分、向量化与持久化逻辑。
- `retrieval`：向量检索、BM25 融合、交叉编码器重排、MMR 去冗流程。

## 模块拆分概览

| 模块 | 主要职责 |
| --- | --- |
| `config.py` | 统一从动态设置服务获取配置；通过 `_read_setting` 提供边界校验与默认值。 |
| `embeddings.py` | 首次使用时加载 `SentenceTransformer` 和 `CrossEncoder`，并缓存实例；提供 `reset_models_for_tests()`。 |
| `ingestion.py` | `ingest_document_file/content`、`update_chunk`、`delete_chunk`；通过 `split_elements` 及 `get_embedder()` 生成向量。 |
| `retrieval.py` | `search_similar_chunks`、`RetrievedChunk`；封装向量召回、BM25 融合、重排、MMR 等步骤。 |

`service.py` 仅重新导出这些接口，外部调用方无需感知内部结构调整。

## 关键流程摘要

### 文档摄入（`ingestion.py`）
1. **提取**：`extract_from_bytes` / `extract_from_text` → `ExtractedElement`。
2. **分割**：`split_elements` 依据动态配置和语言/代码信息生成 `SplitChunk`。
3. **向量化**：`get_embedder().encode` 批量生成归一化向量。
4. **落库**：`crud_knowledge_base.bulk_create_document_chunks` 与全文检索向量更新。
5. **更新**：`update_chunk` 自动重算向量与 `search_vector`，同时刷新语言元数据。

### 检索（`retrieval.py`）
1. **加载配置**：`build_rag_config` 根据动态设置和请求 `top_k` 计算检索参数。
2. **向量召回**：调用 `crud_knowledge_base.fetch_chunk_candidates_by_embedding`。
3. **BM25 融合**：`_apply_bm25_fusion` 在向量候选基础上注入全文检索得分。
4. **重排**：若启用，使用 `get_reranker()` 运行 CrossEncoder，结合粗排得分得到最终 `score`。
5. **MMR**：`_mmr_select` 在相关性与多样性之间权衡输出最终候选集。

### 语言处理（`language.py`）
统一提供：
- `normalize_language_value`
- `detect_language` / `detect_language_meta`
- `is_probable_code` / `is_cjk_text`
- `lingua_status`

该模块避免了此前 `language_utils.py` 与 `ingest_language.py` 的重复逻辑。

## 下一步建议
- 为 `ingestion` 与 `retrieval` 增加细粒度单元测试，配合 `reset_models_for_tests()` 注入轻量模型。
- 将检索流程拆分为可组合的 pipeline 阶段（例如矢量召回、融合、重排、MMR 单独函数）以便于复用与测试。
- 文档层面补充新的模块结构概览，指导开发者在何处扩展新策略或调整配置。
