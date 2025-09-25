# 在现有 RAG 系统中融合 BM25 的实装指南

本文档给出在当前项目中新增 BM25 关键字检索，并与既有的向量检索流程融合的详细步骤。流程自上而下涵盖模型、数据、服务、接口、配置、部署与测试，旨在成为完整的实施手册。

---

## 1. 技术路线概述

1. **检索双路召回**：保留现有的向量相似度召回，新增基于 BM25 的关键字召回，两路候选合并后统一进入重排 / MMR 流程。
2. **数据存储**：利用 PostgreSQL 原生全文检索（`tsvector` + GIN 索引）或引入 `rank-bm25` 等库构建倒排索引。本指南以 PostgreSQL FTS 方案为主。
3. **配置化策略**：通过动态配置或环境变量控制 BM25 召回数量、权重、启停开关等，以便线上快速调参。
4. **兼容现有接口**：REST API 的对外契约保持兼容，除非需要让调用方调节策略，新增参数均设默认值。

---

## 2. 数据层改造

### 2.1 模型定义与迁移

1. **修改文件**：`backend/app/modules/knowledge_base/models.py`
   - 在 `KnowledgeChunk` 模型中新增 `search_vector` 字段，类型为 `sqlalchemy.dialects.postgresql.TSVECTOR`。
   - 为文本字段（如 `content`）提供触发器或监听器，确保插入/更新时同步生成 `tsvector`。

2. **新增迁移**：`backend/alembic/versions/<timestamp>_add_search_vector_to_chunks.py`
   - 在 `upgrade()` 中添加 `search_vector` 列并创建 GIN 索引，例如：
     ```python
     op.add_column(
         "knowledge_chunks",
         sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
     )
     op.execute("UPDATE knowledge_chunks SET search_vector = to_tsvector('simple', content)")
     op.create_index(
         "ix_knowledge_chunks_search_vector",
         "knowledge_chunks",
         ["search_vector"],
         postgresql_using="gin",
     )
     ```
   - 在 `downgrade()` 中删除索引与列。

3. **触发器/函数（可选）**：若希望由数据库自动维护 `tsvector`，可在迁移中创建 `to_tsvector` 触发器。否则由应用层写入。

### 2.2 数据写入流程

1. **修改文件**：`backend/app/modules/knowledge_base/repository.py`
   - 在 `crud_knowledge_base.bulk_create_document_chunks` 等写入函数中，生成 `to_tsvector('simple', chunk.content)` 并填充到 `search_vector` 字段。
   - 若采用数据库触发器，则保证插入时字段为 `None` 即可。

2. **切分管线**：若需要对内容做额外清洗、分词或停用词处理，可在 `backend/app/modules/knowledge_base/ingest_splitter.py` 或对应的预处理模块中扩展逻辑。

---

## 3. 仓储层（Repository）扩展

1. **修改文件**：`backend/app/modules/knowledge_base/repository.py`
   - 新增函数 `search_by_bm25(session, query, limit, filters)`：
     * 使用 `func.ts_rank_cd` 或 `func.ts_rank` 基于 `search_vector` 进行排名。
     * 支持与现有过滤条件一致（知识库 ID、语言、标签等）。
     * 返回 `KnowledgeChunk` 与 BM25 分数。
   - 调整已有的检索函数签名，使其可以返回更多元数据（例如新增 `bm25_score` 字段）。

2. **公共 DTO**：如果服务层需要统一的数据结构，可在 `backend/app/modules/knowledge_base/service.py` 中的 `RetrievedChunk` 增加 `bm25_score` 字段。

---

## 4. 服务层融合逻辑

### 4.1 动态配置

1. **修改文件**：`backend/app/core/config.py`
   - 新增默认配置项，例如 `BM25_ENABLED`, `BM25_TOP_K`, `BM25_WEIGHT`, `BM25_MIN_SCORE` 等。

2. **修改文件**：`backend/app/infrastructure/dynamic_settings.py`
   - 确保上述配置可以通过动态配置服务读取/更新。

### 4.2 检索流程调整

1. **修改文件**：`backend/app/modules/knowledge_base/service.py`
   - 在 `search_similar_chunks` 中：
     * 判断 BM25 是否启用（来自配置或请求参数）。
     * 调用仓储层新增的 `search_by_bm25` 获取候选集合，按照 `BM25_TOP_K` 限制数量。
     * 将 BM25 候选与向量召回候选合并，构造统一的 `RetrievedChunk` 列表。
     * 为 BM25 候选设置 `coarse_score` 或新的 `bm25_score` 字段，作为融合时的初始得分。
     * 在融合阶段（向量分数归一化、重排、MMR）前，利用 `BM25_WEIGHT` 将关键字分数与向量分数线性组合或采用学习到的融合策略。
   - 若向量与 BM25 召回存在重复 chunk，按得分最高者保留或进行分数加权。

2. **MMR / 重排适配**：确认 `_mmr_select` 与重排逻辑使用的是统一的 `score` 字段，必要时在计算总分后更新该字段。

3. **日志与监控**：增加日志记录，输出 BM25 候选数量、融合权重、最终入选来源占比，方便调试。

### 4.3 线程池与模型加载

BM25 不涉及模型加载，但若引入额外库（如自定义分词），需在模块顶部初始化时注意线程安全及懒加载策略，与现有 `_model`、`_reranker` 逻辑一致。

---

## 5. API 层改造

1. **修改文件**：`backend/app/api/v1/endpoints/knowledge_base.py`
   - 在检索接口的请求模型中新增可选参数，例如 `bm25_weight`, `bm25_top_k`, `bm25_enabled`。
   - 将参数透传给 `search_similar_chunks`，保持默认值与现有行为一致（即不开启 BM25）。

2. **请求/响应模型**：
   - 若需要在响应中区分命中来源，可在 `backend/app/schemas/knowledge_base.py` 中新增字段，如 `retrieval_source`、`bm25_score`。

3. **文档更新**：更新 FastAPI OpenAPI 描述，保证前端或调用方了解新参数及默认值。

---

## 6. 依赖与环境

1. **数据库配置**：确保 PostgreSQL 已启用 `pg_trgm` 与 `fuzzystrmatch` 扩展（如需要），在迁移中执行 `CREATE EXTENSION IF NOT EXISTS`。
2. **Python 依赖**（若使用第三方 BM25 库）：
   - 修改 `backend/pyproject.toml` 或 `backend/requirements.txt`，添加 `rank-bm25`、`jieba` 等依赖。
   - 同步更新 `poetry.lock` 或 `requirements.lock`。
3. **Docker 镜像**：更新 `backend/Dockerfile`，确保安装新增依赖，并执行 `alembic upgrade` 时包含新迁移。

---

## 7. 前端联动（可选）

如需让用户选择检索模式或查看召回来源：
1. 修改 `frontend` 下的检索页组件，新增切换选项或展示标签。
2. 更新 `frontend/src/services` 中的 API 调用函数，兼容新增参数。
3. 在 UI 上展示返回的 `bm25_score`、`retrieval_source` 等信息。

若前端无需改动，可跳过此步骤。

---

## 8. 测试策略

1. **单元测试**：
   - 新增 `backend/app/tests/modules/knowledge_base/test_bm25_repository.py`，验证仓储查询能按关键字召回并排序。
   - 新增 `backend/app/tests/modules/knowledge_base/test_bm25_service.py`，覆盖融合逻辑、权重策略、重复去重等。

2. **集成测试**：
   - 在 `backend/app/tests/api/test_knowledge_base_search.py` 中增加带 BM25 参数的 API 测试。
   - 使用固定数据集，验证关键字严格匹配场景下的召回质量。

3. **性能测试**：
   - 在 staging 环境进行压力测试，对比开启/关闭 BM25 的平均延迟、吞吐量。

4. **回归测试**：
   - 确保原有向量检索、重排流程在默认配置下无回归。

---

## 9. 运维与上线流程

1. **迁移执行**：上线前在数据库执行 Alembic 迁移，确保 `tsvector` 列与索引就绪。
2. **配置发布**：通过动态配置中心或环境变量开启 BM25，并设置合适的 `top_k` 与权重。
3. **灰度验证**：
   - 在灰度环境开启 BM25，观察日志与监控指标。
   - 收集真实查询的命中率、满意度反馈。
4. **回滚方案**：若需快速回滚，可在配置层关闭 BM25；如需彻底移除，可执行迁移的 `downgrade()`。

---

## 10. 验收清单

- [ ] Alembic 迁移已执行，`knowledge_chunks` 表存在 `search_vector` 列及 GIN 索引。
- [ ] 仓储层 `search_by_bm25` 能返回正确的 BM25 排序结果。
- [ ] 服务层可根据配置启用/禁用 BM25，并正确融合分数。
- [ ] API 接口兼容旧参数，新参数可控且文档更新。
- [ ] 新增依赖在 Docker 镜像与 CI 流程中通过。
- [ ] 自动化测试通过，覆盖主要路径。
- [ ] 观察期内监控正常，无显著性能回退。

---

完成以上步骤后，即可在现有 RAG 检索系统中稳定引入 BM25 关键字检索能力，并与向量召回协同工作。
