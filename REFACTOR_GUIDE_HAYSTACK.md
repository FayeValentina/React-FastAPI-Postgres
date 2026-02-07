# RAG 重构指导方案（Table 精简 + Haystack 替换）

## 1. 目标

本次重构分两步执行：

1. 精简 `backend/app/modules/llm/models.py` 与 `backend/app/modules/knowledge_base/models.py` 中的表结构，删除低价值字段，降低维护成本。
2. 用 Haystack 替代现有 RAG 管道，实现检索与生成链路组件化，减少自研代码量。

---

## 2. 执行原则

- 先“低风险收敛”，再“架构替换”。
- 保持 API 路径与前端调用尽量不变，优先内部替换。
- 采用双引擎并行（`legacy` / `haystack`）与开关切流，避免一次性切换。
- 每一步都可回滚（代码回滚 + DB migration 可逆或补偿）。

---

## 3. Phase 1：表结构精简（先做）

### 3.1 目标范围

优先精简 `knowledge_documents`，`knowledge_chunks` 暂不大动，`llm` 仅做小改。

### 3.2 建议字段调整

#### A. `knowledge_documents`（第一批删除）

文件：`backend/app/modules/knowledge_base/models.py`

- 删除字段：`language`, `mime`, `checksum`, `meta`
- 保留字段：
  - `id`
  - `source_type`
  - `source_ref`
  - `title`
  - `tags`
  - `created_by`
  - `created_at`

#### B. `knowledge_chunks`（暂不改核心字段）

保留：`embedding`, `search_vector`, `language`（旧链路仍在使用，避免先删后补）

#### C. `llm`（小步精简）

文件：`backend/app/modules/llm/models.py`

- 可先删除：`messages.updated_at`
- 暂不删除：
  - `messages.request_id`
  - `messages.message_index`
  - `conversations.model`, `temperature`, `system_prompt`, `summary`, `title`

### 3.3 必改代码清单

- 后端 schema：
  - `backend/app/modules/knowledge_base/schemas.py`
- 后端 repository：
  - `backend/app/modules/knowledge_base/repository.py`
- 前端类型：
  - `frontend/src/types/knowledge.ts`
- 前端页面：
  - `frontend/src/components/Knowledge/CreateDocumentModal.tsx`
  - `frontend/src/pages/KnowledgeDocumentDetailPage.tsx`
- 数据库迁移：
  - 新增 Alembic migration（drop columns）

### 3.4 验收标准（Phase 1）

- `knowledge` 文档增删改查、入库、检索 API 可正常调用。
- 前端知识库页面不再展示已删除字段。
- Alembic `upgrade` / `downgrade` 可执行。

---

## 4. Phase 2：Haystack 替换 RAG 管道

### 4.1 保留与替换边界

保留：

- FastAPI 路由层
- TaskIQ 调度
- SSE 推送机制
- 会话/消息表（`conversations`, `messages`）

替换：

- 知识入库（extract/split/embed/write）
- 检索（vector / keyword / hybrid）
- 生成编排（prompt + chat generator）

### 4.2 新模块建议

新增目录：`backend/app/modules/rag_haystack/`

建议文件：

- `document_store.py`：初始化 `PgvectorDocumentStore`
- `index_pipeline.py`：入库 Pipeline
- `query_pipeline.py`：查询 Pipeline（hybrid + generator）
- `mapper.py`：Haystack Document 与现有 DTO 映射
- `service.py`：给现有 endpoint/task 提供统一调用入口

### 4.3 组件映射（旧 -> 新）

- 旧：`knowledge_base/ingest_extractor.py`, `ingest_splitter.py`, `embeddings.py`, `ingestion.py`
  - 新：`DocumentCleaner` + `DocumentSplitter` + `SentenceTransformersDocumentEmbedder` + `DocumentWriter`
- 旧：`knowledge_base/retrieval.py`
  - 新：`SentenceTransformersTextEmbedder` + `PgvectorEmbeddingRetriever` + `PgvectorKeywordRetriever` + `DocumentJoiner`
- 旧：`llm/client.py` + `llm/service.py` 中部分 prompt 拼接
  - 新：`ChatPromptBuilder` + `OpenAIChatGenerator`

### 4.4 接入改造点

- `backend/app/api/v1/endpoints/knowledge.py`
  - 保持路由不变，内部调用改为 `rag_haystack.service`
- `backend/app/modules/llm/task.py`
  - 保持 TaskIQ + SSE 逻辑，检索与生成改调 Haystack pipeline

### 4.5 切流策略（必须）

- 新增环境变量：`RAG_ENGINE=legacy|haystack`
- 顺序：
  1. 先切 `knowledge/search`
  2. 再切 chat 主流程
  3. 观察稳定后删除旧链路代码

### 4.6 Phase 2 验收标准

- 同一批测试问题下，Haystack 结果可用，且接口协议不变。
- SSE 事件序列完整（`progress` -> `citations` -> `delta` -> `done`）。
- 旧引擎可一键回退（改 `RAG_ENGINE` 并重启）。

---

## 5. 里程碑计划

### Milestone 1（1-2 天）

- 完成 `knowledge_documents` 字段精简
- 打通 migration + 前后端字段同步

### Milestone 2（2-4 天）

- 完成 Haystack indexing/query pipeline
- 在 `knowledge/search` 启用 `RAG_ENGINE` 双轨

### Milestone 3（2-4 天）

- 将 chat 任务链路切到 Haystack
- 保留 SSE 与会话持久化逻辑

### Milestone 4（1-2 天）

- 删除旧 RAG 代码
- 更新文档与测试，完成收尾

---

## 6. 回滚策略

- 代码回滚：按里程碑分 PR，逐步合入，出现问题回滚对应 PR。
- 数据回滚：每个 migration 保留 downgrade；若删除列无法安全恢复业务语义，先做“软下线（不再读写）”再物理删除。
- 流量回滚：将 `RAG_ENGINE` 切回 `legacy`。

---

## 7. 风险与注意事项

- 不要在切到 Haystack 前先删除 `knowledge_chunks` 关键字段（如 `embedding/search_vector`）。
- `llm/task.py` 中 SSE 与事务逻辑复杂，替换时仅替换“检索+生成”子流程，避免动消息持久化与事件发布框架。
- 先保证接口兼容，再做内部收敛。

---

## 8. 后续执行建议

1. Phase 1 固定删除字段：`language`, `mime`, `checksum`, `meta`。
2. 按 Milestone 1 开始改造并提交第一批 migration。
3. 建立 `RAG_ENGINE` 开关后再启动 Haystack 接入，避免一次性大改。
