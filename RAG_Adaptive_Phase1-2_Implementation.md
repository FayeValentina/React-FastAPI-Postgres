# RAG 自适应检索改造（阶段 1 & 阶段 2）实装指南

> 适用范围：`backend/app/modules/knowledge_base/service.py` 及其依赖的配置、API、测试代码。

本指南面向需要在现有检索模块上落地阶段 1（Cross-Encoder 重排 + 智能 `top_k`）和阶段 2（查询感知的参数调节）改造的工程师，按“配置 → 代码 → 校验 → 运维”的顺序列出实施步骤与注意事项。

---

## 1. 改造目标概览

| 阶段 | 能力 | 关键指标 |
| --- | --- | --- |
| 阶段 1 | 引入双塔召回 + Cross-Encoder 重排；将返回数量约束从“固定 `top_k`”升级为“`top_k` 上限 + 分数阈值” | 提升结果相关度、降低噪声 |
| 阶段 2 | 基于查询意图调整 `RAG_MMR_LAMBDA` 与相关性阈值（向量相似度与重排分数） | 让多样性与精度随查询类型自适应 |

---

## 2. 前置准备

1. **依赖**
   - `sentence-transformers>=2.2` 已包含 Cross-Encoder；若生产镜像未安装，请在 `backend/pyproject.toml` 中追加 `"sentence-transformers[torch]"` GPU/CPU 依赖，并在镜像构建阶段预下载权重（可通过 `python -c "from sentence_transformers import CrossEncoder; CrossEncoder('BAAI/bge-reranker-base')"` 实现热身）。
   - 观察部署环境 CPU/GPU 情况，预估 Cross-Encoder 推理耗时（CPU 约 120ms/样本，GPU <10ms），决定是否开启默认值。

2. **配置管理**
   - 所有新增参数需在 `Settings`、`dynamic_settings_defaults()`、`DynamicSettingsService`、`admin_settings` API 中同步。
   - 建议新增参数表：

     | 键名 | 含义 | 默认值建议 |
     | --- | --- | --- |
     | `RAG_RERANK_ENABLED` | 是否启用重排 | `False`（便于灰度） |
     | `RAG_RERANK_MODEL` | Cross-Encoder 模型名 | `"BAAI/bge-reranker-base"` |
     | `RAG_RERANK_CANDIDATES` | 召回后送入重排的候选上限 | `50` |
     | `RAG_RERANK_BATCH_SIZE` | 重排推理批量 | `8` |
     | `RAG_RERANK_SCORE_THRESHOLD` | 重排分数阈值 | `0.5` |
     | `RAG_RERANK_SCORE_FALLBACK` | 阈值过滤后为空时的兜底返回数 | `min(2, top_k)` |
     | `RAG_DYNAMIC_LAMBDA_ENABLED` | 是否启用 λ 自适应 | `False` |
     | `RAG_DYNAMIC_THRESHOLD_ENABLED` | 是否启用阈值自适应 | `False` |
     | `RAG_QUERY_KEYWORDS_PROFILE` | 自适应策略的关键字配置 | 见 §4.1 |

   - 关键字配置可存 JSON（例：`{"broad": ["总结","compare"], "focused": ["如何","步骤"]}`）或在代码中写死默认并允许动态覆盖。

3. **结构留意**
   - 目前 `_model`（向量模型）在模块级加载，Cross-Encoder 需同样懒加载并通过 `run_in_threadpool` 调用，避免阻塞事件循环。
   - `search_similar_chunks` 已具备动态配置能力，新增逻辑应尽量在该函数内部完成，以保证 API/WS 入口无需大改。

---

## 3. 阶段 1 实装细则

### 3.1 新增/调整配置

1. 在 `backend/app/core/config.py` 的 `Settings` 中加入表 2 的新字段，并在 `dynamic_settings_defaults()` 返回字典里补齐默认值。
2. 扩充 `backend/app/modules/admin_settings/schemas.py`、`crud` 与 API 层，允许前端管理新参数。
3. 为部署环境增加 env 示例（`.env.dev` / `.env.prod`）说明新参数。

### 3.2 Cross-Encoder 重排模块

1. **模型懒加载**（位于 `service.py` 顶部，靠近 `_model`）：

   ```python
   from sentence_transformers import CrossEncoder
   from threading import Lock

   _rerank_model: CrossEncoder | None = None
   _rerank_lock = Lock()

   def _get_rerank_model() -> CrossEncoder:
       if _rerank_model is None:
           with _rerank_lock:
               if _rerank_model is None:
                   _rerank_model = CrossEncoder(settings.RAG_RERANK_MODEL, device=settings.RAG_RERANK_DEVICE)
       return _rerank_model
   ```

   - `RAG_RERANK_DEVICE` 可选配置，默认为 `"cpu"`。
   - 封装 `async def _rerank_pairs(pairs: list[tuple[str, str]]) -> list[float]`，内部 `await run_in_threadpool(_get_rerank_model().predict, pairs, batch_size)`。

2. **候选构建**：在 `_mmr_select` 调用前新增重排入口。
   - 先计算 `rerank_limit = min(len(filtered), rerank_candidates)`。
   - 构造 `[ (query, chunk.chunk.content) for chunk in filtered[:rerank_limit] ]`。
   - 将结果分数写回 `RetrievedChunk.score`（可另存 `rerank_score` 字段，保持原始向量分数以兜底）。
   - 若模型失败（下载/推理异常），捕获日志并回退到原逻辑。

3. **阈值过滤与返回**
   - 在重排后执行：`passed = [item for item in filtered if item.score >= threshold]`。
   - 若 `passed` 为空且配置了 `RAG_RERANK_SCORE_FALLBACK`，则按照原排序返回 `fallback_count` 个候选，并打 warning。
   - 最终将 `selected = _mmr_select(passed, min(top_k, len(passed)), ...)`；`top_k` 依旧作为上限。

4. **性能与缓存**
   - 在阶段上线初期记录 `len(candidates)`, `len(passed)`, `elapsed_ms`，可使用 `logging` 或 Prometheus 指标。
   - 对高频查询，可在 `DynamicSettingsService` 外层加 LRU/Redis 缓存（可后续扩展）。

### 3.3 API 行为调整

1. REST `POST /knowledge-base/search` 若已有 `top_k` 参数，无需新增；仅需在响应结构中可选返回 `rerank_score`，方便前端调试。
2. 若结果为空，应返回提示信息（例如 `"No chunks met rerank threshold"`），前端据此引导用户放宽条件。

### 3.4 测试与验证

1. **单元测试**
   - 新增重排逻辑的伪模型（例如固定返回 [0.9, 0.2, ...]）来验证阈值过滤与 Fallback 行为。
   - 为 `DynamicSettingsService` 新参数添加 round-trip 测试。
2. **集成测试**
   - 模拟 API 调用，确保当阈值高于所有候选时会走 fallback。
3. **性能验证**
   - 使用 10~50 并发对最常见查询压测，确保 P95 延迟满足 SLA；必要时开启 `RAG_RERANK_ENABLED=False` 兜底。

---

## 4. 阶段 2 实装细则

### 4.1 查询意图识别

1. 新增 `backend/app/modules/knowledge_base/query_profile.py`（建议新文件）定义：
   - `Enum('QueryIntent', 'UNKNOWN BROAD FOCUSED TROUBLESHOOT DOC_SPECIFIC')`。
   - `class QueryProfiler`：接收关键字配置（来自动态设置或默认字典），提供 `classify(query: str) -> QueryIntent`。
   - 默认规则示例：
     ```json
     {
       "broad": ["总结", "比较", "overview", "tell me", "介绍"],
       "focused": ["如何", "步骤", "原因", "是什么", "定义"],
       "troubleshoot": ["报错", "error", "failed", "解决"],
       "doc_specific": ["这份", "该文档", "above file"]
     }
     ```
   - 提供简单的多语言大小写兼容处理（`lower()`、中文保持原样）。

2. 在 `service.py` 中懒加载 `QueryProfiler`，并允许通过动态配置覆盖关键字。

### 4.2 动态 MMR λ

1. 在 `search_similar_chunks` 内取得 `intent = profiler.classify(query)`。
2. `mmr_lambda_base = _coerce_config_value(..., "RAG_MMR_LAMBDA", ...)` 保留。
3. 根据意图调整：
   - `BROAD`：`mmr_lambda = clamp(base - 0.15, 0.3, 0.9)`。
   - `FOCUSED` / `TROUBLESHOOT`：`mmr_lambda = clamp(base + 0.15, 0.1, 0.95)`。
   - 其他：保持默认。
4. 增加配置 `RAG_DYNAMIC_LAMBDA_ENABLED` 控制是否启用该逻辑。
5. 记录调节后的 λ 以便调试，可在 `RetrievedChunk` 上添加 `metadata` 或在日志中输出。

### 4.3 动态阈值

1. **向量相似度阈值 (`min_sim`)**：
   - `broad` 查询：`min_sim = max(0.0, base - 0.05)`。
   - `focused` / `troubleshoot`：`min_sim = min(1.0, base + 0.05)`。
   - `doc_specific`：上调 `per_doc_limit`，详见 §4.4。
2. **重排分数阈值**（需在阶段 1 已落地的前提下）：
   - 类似策略，可定义 `threshold_delta`（默认 ±0.05），并通过配置暴露。
   - 若阈值调整后导致返回 0 条且 Fallback 被触发，应在日志中标记，以便观察策略是否过于激进。
3. 配置开关：`RAG_DYNAMIC_THRESHOLD_ENABLED`。

### 4.4 同文档限制联动（可选）

- 当 `intent == QueryIntent.DOC_SPECIFIC` 时，可将 `per_doc_limit = max(per_doc_limit, 3)` 或允许一次返回同文档更多片段。
- 若需要用户显式指定文档，可在请求体中添加 `document_id` 并在阶段 3 实现更完整的策略；阶段 2 可先在服务器侧识别语义触发。

### 4.5 代码组织建议

1. 将所有“调节逻辑”封装为独立函数：
   - `_adjust_mmr_lambda(base: float, intent: QueryIntent, enabled: bool) -> float`
   - `_adjust_thresholds(base_sim: float, base_rerank: float, intent: QueryIntent, enabled: bool) -> tuple[float, float]`
   便于单元测试与后续扩展。
2. 在 `search_similar_chunks` 中调用上述函数，保持主流程可读性。
3. 对新函数写独立测试，覆盖关键字匹配、大小写、空字符串、未知语言等情况。

### 4.6 动态配置联动

1. `DynamicSettingsService.get_all()` 返回后，先读取 `RAG_QUERY_KEYWORDS_PROFILE`，如存在则覆盖默认关键字。
2. 可允许通过管理后台实时更新关键字，便于无代码调整策略。

### 4.7 验证方案

1. **单元测试**：
   - 针对不同查询断言 `mmr_lambda`/`min_sim` 调整正确。
   - 检测开关关闭时所有值保持原状。
2. **集成测试**：
   - 构造“简单问题”、“总结型问题”、“报错排查问题”三类查询，验证返回的 chunk 数量、来源多样性、排序稳定性。
3. **监控**：
   - 记录调整后的参数值、最终返回的 chunk 数量，便于后续分析是否需要重训关键字或改进分类器。

---

## 5. 上线与回滚策略

1. **灰度发布**：
   - 默认将 `RAG_RERANK_ENABLED=False`、`RAG_DYNAMIC_*_ENABLED=False`，通过动态配置对部分实例/租户开启，观察延迟与命中率。
2. **指标观测**：
   - 重点关注：请求总耗时、返回 chunk 数量、空结果率、Fallback 触发次数。
3. **回滚**：
   - 遇到性能问题或结果异常，先通过动态配置关闭重排/自适应；如需彻底回滚，删除新增配置并恢复旧版镜像。

---

## 6. 文档与培训

- 在团队 Wiki 中同步此文档链接，并附上：
  - Cross-Encoder 模型选择表（不同模型大小、速度对比）。
  - 常见问题解答（如：阈值过高导致空结果如何处理、如何扩展关键字等）。
- 建议在前端/运营同学中做一次培训，说明“返回结果数量可能随查询自动变化”的产品行为。

---

## 7. 后续扩展提示

- 若阶段 1、2 表现稳定，可继续实现阶段 3（会话级策略）时复用本阶段的意图分类器与动态配置框架。
- 可考虑加入查询画像缓存、用户画像（行业/角色）等维度，进一步精细化阈值与 λ 的调整。

