# RAG 自适应与重排升级实装指南

## 背景概述

当前后台的知识库检索模块位于 `backend/app/modules/knowledge_base/service.py`，核心流程如下：

1. **向量召回**：
   - 使用 `SentenceTransformer`（默认 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`）对查询编码。
   - 通过 `crud_knowledge_base.fetch_chunk_candidates_by_embedding` 在 PostgreSQL/pgvector 中检索相似块。
2. **打分与筛选**：
   - 按相似度及语言奖励计算分数。
   - 基于 `RAG_MIN_SIM` 过滤，再使用 `_mmr_select` 做多样性去重（依赖 `RAG_MMR_LAMBDA`、`RAG_PER_DOC_LIMIT`）。
3. **上下文组装**：
   - 在 `backend/app/modules/llm/service.py` 内依据 `RAG_CONTEXT_TOKEN_BUDGET`、`RAG_CONTEXT_MAX_EVIDENCE` 拼装引用。
4. **静态配置来源**：
   - 所有参数默认由 `config.py` 注入，部分值可从 Redis 动态配置覆盖（例如 `RAG_TOP_K`、`RAG_MIN_SIM`）。

这一架构简单可靠，但存在以下痛点：

- **静态参数无法兼容多场景**：不同类型查询对上下文数量、相似度阈值的需求差异大，目前需要手工调参。
- **召回精度受限**：仅依赖 Bi-Encoder 向量召回，噪声块难以过滤，导致 LLM 上下文挤占。
- **模型升级受限**：嵌入模型维度固定为 384，限制了更强模型的使用；重排模型尚未纳入部署流程。

为解决上述问题，本指南规划了“策略层 + Cross-Encoder 重排 + 模型替换”的升级路线，使系统能够根据查询特征自适应调参，并通过重排提升召回质量。

## 1. 总览

- **阶段一：策略层参数判定**——在调用 `search_similar_chunks` 前，根据查询特征动态覆盖 `top_k`、`RAG_PER_DOC_LIMIT`、`RAG_MIN_SIM` 等关键参数。
- **阶段二：Cross-Encoder 重排**——在向量召回后使用 `BAAI/bge-reranker-base` 对候选进行二次排序并按阈值过滤。
- **模型替换：**将嵌入模型切换为 `intfloat/multilingual-e5-base`（768 维）。
- **配置优先级：**策略层 > Redis 动态配置 > settings 默认值。
- **安全开关：**通过 `RAG_STRATEGY_ENABLED` 控制策略层是否生效。

## 2. 准备工作

1. **依赖检查**
   - 后端已使用 `sentence-transformers`；确保运行环境允许下载 `intfloat/multilingual-e5-base` 与 `BAAI/bge-reranker-base`。
   - 若镜像或 CI 无外网，提前在 `docker` 构建脚本或 `scripts/` 中添加模型缓存逻辑。
2. **环境变量与动态配置初始化**
   - `.env.example`、`.env.dev`、`.env.prod`：
     - 更新 `EMBEDDING_MODEL=intfloat/multilingual-e5-base`，注明向量维度 768。
    - 新增 `RERANKER_MODEL=BAAI/bge-reranker-base`（供后端、初始化脚本和缓存使用）。
    - 视需要补充 `HF_TOKEN`、`HF_HOME=/models/hf` 等注释，帮助运维理解离线缓存目录。
     - 提醒：新增变量后，需要确认后端代码（如 `config.py`、策略层或服务模块）已经读取并使用 `RERANKER_MODEL`，避免部署时缺少模型标识。
   - 通过 `backend/app/infrastructure/dynamic_settings/service.py` 的管理接口，向 Redis 写入以下键值（作为部署前准备）：
     - `RAG_STRATEGY_ENABLED=false`
     - `RAG_RERANK_ENABLED=false`（灰度开关）
     - `RAG_RERANK_CANDIDATES=40`
     - `RAG_RERANK_SCORE_THRESHOLD=0.5`
     - `RAG_RERANK_MAX_BATCH=16`
   - 目的：上线时无需改代码即可开启/关闭策略与重排功能，并确保所有模型标识集中在环境变量中。
   - 在 `config.py` 的 `dynamic_settings_defaults()` 中同步加入上述三个重排参数的默认值，并在 Admin 设置界面暴露，确保后续可通过动态配置调参。

3. **Docker Compose 与模型预热**
   - 文件：`docker-compose.dev.yml`、`docker-compose.prod.yml`
     - 在 `backend` 服务的 `environment` 中新增 `RERANKER_MODEL=${RERANKER_MODEL}`，保证应用容器可读取该模型名称。
     - 在 `embeddings_init` 服务的 `environment` 中新增 `RERANKER_MODEL=${RERANKER_MODEL}`，并继续挂载 `models_data:/models`。
     - 如果希望将 embeddings 与 reranker 的预下载分离，可复制一份服务定义（如 `reranker_init`），指向新的脚本；否则扩展现有脚本即可。
   - 脚本：`scripts/embeddings_init.sh`
     - 扩展为同时处理嵌入与重排模型：
       - 读取 `RERANKER_MODEL` 环境变量。
       - 将原有 `snapshot_download` 逻辑包裹在 `for model in "$EMBEDDING_MODEL" "$RERANKER_MODEL"` 循环内，空值则跳过。
       - 为了复用现有 Python 片段，可通过环境变量（例如 `TARGET_MODEL`) 将当前模型 ID 传给内嵌 Python 程序，并在日志中区分 `[embeddings_init]` 与 `[reranker_init]`。
     - 下载完成后打印缓存目录树，便于排查缓存路径是否正确。
     - 如需清理旧版本缓存，可在脚本尾部比较缓存目录与模型列表，删除冗余目录（可选步骤）。
   - 目的：保证两类模型在容器启动前已缓存至共享卷 `/models/hf`，并且后端可通过环境变量定位模型名称。

## 3. 策略层实现步骤（阶段一）

1. **更新 settings 默认值**
   - 文件：`backend/app/core/config.py`
   - 修改内容：
     - 在 `class Settings` 中新增字段 `RAG_STRATEGY_ENABLED: bool = Field(default=False)` 以及 `RAG_RERANK_ENABLED`、`RAG_RERANK_MODEL` 等相关字段。
     - 在 `dynamic_settings_defaults()` 返回值中加入上述新键，确保 Redis 缺失时仍有默认值。
   - 目的：保证策略层与重排的默认行为可控，并与优先级约定保持一致。

2. **新增策略 Helper 模块**
   - 新文件：`backend/app/modules/knowledge_base/strategy.py`
   - 主要函数：
     ```python
     async def resolve_rag_parameters(
         query: str,
         base_config: Mapping[str, Any],
         *,
         request_ctx: StrategyContext,
     ) -> StrategyResult:
         ...
     ```
   - 逻辑要点：
     - 若 `base_config.get("RAG_STRATEGY_ENABLED")` 为假，返回 `StrategyResult(config=dict(base_config), scenario="disabled")`。
     - 启用时：
       - 构造 `StrategyContext`（可包含查询长度、是否指定文档 ID、用户 role 等信息）。
       - 通过启发式规则判定场景：宽泛、精确、模糊等。
       - 生成 `overrides`，示例：
         - 宽泛 → `top_k = min(base_top_k + 4, 12)`、`RAG_PER_DOC_LIMIT = max(3, base_per_doc_limit)`、`RAG_MIN_SIM = max(0.2, base_min_sim - 0.1)`；并提升检索深度与上下文容量（`RAG_OVERSAMPLE ≥ 7`、`RAG_MAX_CANDIDATES ≥ top_k*12`、`RAG_RERANK_CANDIDATES ≥ top_k*6`、`RAG_CONTEXT_MAX_EVIDENCE ≥ 18`、`RAG_CONTEXT_TOKEN_BUDGET ≥ 2800`），同时放宽重排阈值至 `≤0.45`。
         - 精确 → `top_k = max(3, base_top_k - 2)`、`RAG_PER_DOC_LIMIT = max(5, base_per_doc_limit)`、`RAG_MIN_SIM = min(0.9, base_min_sim + 0.15)`；收紧检索范围（`RAG_OVERSAMPLE ≤ 3`、`RAG_MAX_CANDIDATES ≤ 80`、`RAG_RERANK_CANDIDATES ≤ top_k*3`）、提高重排阈值到 `≥0.6`，并下调上下文预算至 ~1800 tokens。
         - 指定文档 → 强调深挖同一文档（`RAG_PER_DOC_LIMIT ≥ 6`、`RAG_OVERSAMPLE ≥ 6`、`RAG_MAX_CANDIDATES ≥ 160`、`RAG_RERANK_CANDIDATES ≥ 120`），同时扩大上下文窗口（`RAG_CONTEXT_MAX_EVIDENCE ≥ 16`、`RAG_CONTEXT_TOKEN_BUDGET ≥ 2600`）。
         - QA 场景 → 相较默认略增 `top_k` 与 oversample，重排候选提升至 `top_k*5`，并将上下文预算提升到 2400 左右以便回答要点问题。
       - 合并结果并返回 `StrategyResult(config=merged, overrides=overrides, scenario=scenario)`。
   - 目的：集中管理策略逻辑，并为日志/测试提供结构化输出。

3. **接入 FastAPI 端点与 WebSocket**
   - 文件：
     - `backend/app/api/v1/endpoints/llm_ws.py`
     - `backend/app/api/v1/endpoints/knowledge.py`
   - 修改步骤：
     1. 在文件顶部导入 `resolve_rag_parameters` 与 `StrategyContext`。
     2. 获取 `config` 后，调用策略 helper：
        ```python
        strategy = await resolve_rag_parameters(
            user_text,
            config,
            request_ctx=StrategyContext(
                top_k_request=incoming.get("top_k"),
                document_id=incoming.get("document_id"),
                channel="websocket",
            ),
        )
        strategy_config = strategy.config
        ```
     3. 使用 `strategy_config` 调用 `search_similar_chunks`。
     4. 将 `strategy.scenario`、`strategy.overrides` 写入日志（例如 `logger.info("rag_strategy", extra=strategy.to_log_dict())`）。
     5. REST 端点中注意保留请求体中的 `top_k`（可作为 `request_ctx.top_k_request`，策略可根据它决定是否覆盖）。
   - 目的：在现有入口处统一启用策略层，并提供可观测性。

4. **失败与回退设计**
   - `strategy.py` 中捕获所有异常，记录 warning 并返回原始 `base_config`。
   - 如果策略将 `top_k`、`RAG_PER_DOC_LIMIT` 等算出非法值（<=0），需回退到 `base_config` 值。
   - 在单元测试中验证异常路径，确保不会阻塞主流程。

## 4. Cross-Encoder 重排实现步骤（阶段二）

1. **模型加载与配置**
   - 文件：
     - `backend/app/core/config.py`：新增字段 `RAG_RERANK_ENABLED: bool = Field(default=False)`、`RAG_RERANK_MODEL: str = Field(default="BAAI/bge-reranker-base")`、`RAG_RERANK_CANDIDATES`, `RAG_RERANK_SCORE_THRESHOLD`, `RAG_RERANK_MAX_BATCH`。
     - `backend/app/modules/knowledge_base/service.py`：导入 `CrossEncoder` 并实现懒加载函数 `_get_reranker()`。
   - 目的：让重排模型的选择、开关、阈值全部通过统一配置管理。

2. **扩展检索流程**
   - 修改 `search_similar_chunks`：
     1. 读取 `config_map.get("RAG_RERANK_ENABLED")`，若为假直接走原逻辑。
     2. 若为真，将 `oversample` 计算改为 `max(top_k * oversample_factor, RAG_RERANK_CANDIDATES)`。
     3. 将候选列表整理为 Cross-Encoder 输入，建议格式：`[[query, chunk_preview], ...]`；其中 `chunk_preview` 可为内容前 512 个字符，防止过长。
     4. 使用 `await run_in_threadpool(_get_reranker().predict, pairs, convert_to_numpy=True)` 获取得分；必要时对 logits 做 `scipy.special.expit`。
     5. 把得分写入 `RetrievedChunk.score`（或新增字段 `rerank_score` 并在排序时优先使用）。
     6. 过滤分数低于 `RAG_RERANK_SCORE_THRESHOLD` 的候选；若全部被过滤掉则回退到原始候选。
     7. 按新分数排序后，再执行 `_mmr_select`，以兼顾多样性和重排质量。
   - 目的：保持原有 MMR 与语言奖励机制，只替换打分来源。

3. **批量与异常处理**
   - 在 `service.py` 中实现一个局部工具函数 `_batched(items, size)` 以 `RAG_RERANK_MAX_BATCH` 分批预测。
   - 捕获 Cross-Encoder 预测过程中的异常（模型加载失败、显存不足等），记录日志并回退到无重排流程。
   - 若未来需要用 GPU，可在 `_get_reranker` 中支持 `device` 参数。

4. **日志与监控扩展**
   - 在 `search_similar_chunks` 末尾添加调试日志（debug 级别），记录：`rerank_enabled`、候选数量、过滤前后数量、平均得分、耗时。
   - 在 `monitoring`（若有 Prometheus）中新增直方图：`rag_rerank_duration_seconds`、`rag_rerank_candidate_count`。

5. **管理员界面**
   - 文件：`frontend/src/components/AdminSettings/settingDefinitions.ts`
   - 在设置项中新增上述配置的表单控件，说明用途及推荐范围。
   - 目的：方便非开发人员直接通过前端控制开关与阈值。

## 5. 嵌入模型替换（multilingual-e5-base）

1. **配置与模型加载**
   - 更新 `.env*` 的 `EMBEDDING_MODEL` 为 `intfloat/multilingual-e5-base`。
   - 保持 `SentenceTransformer` 懒加载逻辑不变。

2. **数据库列宽修改**
   - `backend/app/modules/knowledge_base/models.py` 中的 `Vector(dim=384)` 改为 `Vector(dim=768)`。
   - 创建 Alembic 迁移，执行 SQL：`ALTER TABLE knowledge_chunks ALTER COLUMN embedding TYPE vector(768);`
   - 迁移完成后需要重新写入向量，请确保数据库与模型一致。

3. **数据重嵌入**
   - 编写脚本遍历现有 `KnowledgeChunk`，使用新模型重新编码，并更新 `embedding` 列。
   - 对应文档标题/语言等元数据也可同步更新（可选）。
   - 在切换期间需要停用检索或在后台异步完成再切换。

4. **向量索引配置**
   - 若使用 `ivfflat` 索引，需要重新构建索引（删除旧索引 → 新向量入库 → 重建）。
   - 调整 `RAG_IVFFLAT_PROBES` 等参数时需重新压测。

## 6. 回归与测试

- **单元测试**
  - 新文件：`backend/app/modules/knowledge_base/tests/test_strategy.py`
    - 覆盖宽泛/精确/混合输入、Redis 关闭开关、异常回退等场景；验证输出配置与预期匹配。
  - 更新（或新增）`backend/app/modules/knowledge_base/tests/test_service.py`，模拟开启重排时的打分流程（可使用 `monkeypatch` 注入伪 Cross-Encoder）。
- **集成测试**
  - 在 `backend/app/tests/` 下新增端到端用例，模拟 REST/WebSocket 请求，确保策略结果与上下文返回一致。
  - 若使用 pytest fixtures，考虑添加 Redis mock 覆盖动态配置优先级。
- **手动验证**
  - 宽泛问题：例如 “介绍我们所有的 API”，观察是否提升 `top_k` 并返回多来源内容。
  - 精确问题：例如 “redis_pool 超时时间在哪配置”，确认结果集中于同一文档的连续段落。
  - 压测 Cross-Encoder 耗时，确保阈值过滤后的上下文更加精炼。
- **性能测试**
  - 在 `scripts/` 中编写本地压测脚本（可复用现有脚本），对比开关开/关情况下的 P95 延迟。
  - 监控 Redis 调用次数和线程池任务队列情况，提早发现瓶颈。

## 7. 上线与运维建议

1. **灰度开关**：
   - 先启用 `RAG_STRATEGY_ENABLED`，观察几天。
   - 再启用 `RAG_RERANK_ENABLED`，逐步增大 `RAG_RERANK_CANDIDATES`。
2. **监控指标**：
   - 请求量、策略命中率、重排过滤率、上下文平均 token 数。
   - LLM 最终回答满意度（若有用户评分）与失败率。
3. **回滚策略**：
   - 若策略导致质量下降，关闭 Redis 开关即可恢复原有逻辑。
   - 若嵌入模型切换有问题，保留旧模型向量的备份以便回滚。
4. **文档更新**：
   - 更新管理员设置界面（`frontend/src/components/AdminSettings/settingDefinitions.ts`）展示新开关与阈值。
   - 在运维手册中记录新的调参项与常见问题。

---
以上步骤完成后，系统将具备基础的自适应检索能力，并能通过重排显著提升召回质量。后续如需引入更复杂的意图识别或上下文预算策略，可在策略 helper 中继续扩展。
