# 知识库模块冗余与检索流程分析

## 已完成的结构优化
- 统一语言/代码识别：新增 `detect_language_meta`，将 code 判定与语言推断的公共逻辑集中在 `ingest_language`，`tokenizer.py`、`ingest_splitter.py`、`service.py` 等均复用该接口，移除重复的 `is_probable_code`/语言分支维护。
- 文本抽取层（`extract_from_text/bytes`）确保 fallback 生成，`service.py` 不再额外 `_ensure_elements`，减少双重兜底。
- 文档导入端点共用 `_ingest_document`，负责文档存在校验与错误映射，`/ingest` 与 `/ingest/upload` 专注参数和业务调用。

## `llm_ws` 与 `knowledge` 检索流程对比

### 共同点
- 两条路径最终都依赖 `backend/app/modules/knowledge_base/bm25.py:18-74` 的 `fetch_bm25_matches` 返回 `KnowledgeChunk` 与评分元数据。
- 检索结果均被整理成包含内容片段、分数、来源等字段的响应结构，便于调用侧直接展示。

### 差异点
- `knowledge.py:139-210` 走纯 BM25 流程，`score/similarity` 均为归一化 BM25 分数，`retrieval_source` 恒为 `bm25`，无向量召回或重排。
- `llm_ws.py:65-152` 先用 `resolve_rag_parameters` 结合动态配置与意图分类调参，再调用 `search_similar_chunks`（`service.py:520-674`）执行向量召回、语言奖励、BM25 融合、交叉编码重排与 MMR。
- WebSocket 流程支持 `document_id`、`top_k` 等上下文定制，并在 `prepare_system_and_user` 中将检索结果写入模型提示；REST 搜索端点则聚焦轻量检索，直接返回前 `top_k` 条 BM25 结果。
- WebSocket 端对返回内容做 500 字符截断并附带 `key` 标记，REST 端保留完整 chunk 内容，响应目的不同导致格式差异。

## 总结
- REST 搜索端点保持轻量 BM25 定位，同时动态配置可调整 BM25 最低分数与候选上限。
- 语言检测与代码判定现已集中维护；后续如需扩展语言或 code 识别策略，可在 `detect_language_meta` 单点更新，所有调用路径自动受益。

