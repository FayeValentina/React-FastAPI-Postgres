# LLM Query Intent Classifier Rollout Plan

## 1. 背景与目标
- 现有 `_classify_query` 仅依赖启发式规则，无法覆盖复杂/复合查询场景。
- 项目中已集成大语言模型客户端（`backend/app/modules/llm/client.py`），可作为意图分类器。
- 目标：在保持主流程稳定的前提下，引入 LLM 分类结果增强策略层参数自适应能力，实现更细粒度的检索配置与上下文拼装。

## 2. 总体架构
1. **策略入口**：`resolve_rag_parameters` 首先判定是否启用 LLM 分类；若未启用或触发回退，继续走原启发式。
2. **LLM 分类服务**：
   - 新建模块（建议 `backend/app/modules/knowledge_base/intent_classifier.py`）。
   - 提供 `async classify(query: str, ctx: StrategyContext) -> ClassificationResult`。
   - 使用 `AsyncOpenAI` 客户端调用项目现有 LLM。
3. **策略融合**：
   - 支持 LLM 输出 `scenario`、`confidence`、`reason`。
   - 若置信度 < 阈值或返回未知标签，自动回退启发式。
   - 允许 LLM 返回扩展标签，比如 `troubleshooting`、`procedural`, `compare`；策略层根据这些标签映射到检索参数（可保留默认四大类作为兜底）。

## 3. 实施步骤
### 3.1 调研与准备
- 收集真实查询样本并人工标注预期场景，覆盖 REST/WS 渠道、带 `document_id` 的请求等。
- 评估可用模型：优先使用成本低、延迟短的模型（如 gpt-4o-mini / gpt-4.1-mini）。
- 确认调用 QPS、费用预算，必要时加缓存或限流策略。

### 3.2 技术实现
1. **配置新增**（`config.py` + 动态配置）
   - `RAG_STRATEGY_LLM_CLASSIFIER_ENABLED: bool = False`
   - `RAG_STRATEGY_LLM_CLASSIFIER_MODEL: str = "gpt-4o-mini"`
   - `RAG_STRATEGY_LLM_CLASSIFIER_TIMEOUT_MS: int = 2000`
   - 可选：`RAG_STRATEGY_LLM_CLASSIFIER_CONFIDENCE_THRESHOLD`
2. **提示模板设计**
   - 指令样例：
     ```text
     You are a classification assistant. Given a user query and optional metadata, output a JSON object with fields scenario (one of [...]), confidence (0-1).
     ```
   - 输入包含：用户原始问题、是否携带 `document_id`、渠道、历史上下文摘要等。
   - 输出强制 JSON，必要时用 `response_format` / `json_schema` 控制。
3. **分类模块**
   - 构建 `ClassificationResult` dataclass（scenario、confidence、raw_response、source="llm"）。
   - 调用 LLM 时设置超时、重试（建议 1 次重试），并捕获异常返回 `fallback=True`。
   - 针对短查询或明确场景（如 `document_id` 不为空）提供快速绕过，避免无意义调用。
4. **策略层集成**
   - `resolve_rag_parameters` 在启用开关且满足触发条件时调用分类模块。
   - 根据 LLM 返回的标签映射到内部场景（可维护 `LLM_SCENARIO_MAP`）。
   - 追加日志字段：`{"classifier": "llm", "confidence": 0.82}`；在低置信度或回退时记录警告。
   - 保留原 `_classify_query` 作为兜底分支。
5. **监控与指标**
   - 添加统计：调用次数、超时率、平均延迟、各场景分布。
   - 记录误差样本供后续提示词优化。

### 3.3 测试与验证
- **单元测试**：Mock LLM 返回不同标签/异常，验证策略层行为一致；确保回退逻辑覆盖。
- **契约测试**：校验 Prompt 输出的 JSON 结构，在解析失败时自动回退。
- **离线评估**：对标注数据集跑 LLM 分类，计算准确率、召回、场景覆盖率；与启发式对比。
- **性能测试**：测量启用分类后的端到端延迟增量；在预期负载下评估成本。

### 3.4 灰度与上线
1. **配置开关**
   - 首期在非生产环境（staging）开启，并仅对部分渠道（如 WebSocket）启用。
   - 支持将特定用户或租户纳入白名单（可在 `StrategyContext` 增加 `tenant_id` 并结合动态配置）。
2. **灰度策略**
   - 阶段 1：启用但只记录 LLM 结果，不影响实际检索（shadow mode）。
   - 阶段 2：在低风险渠道正式使用 LLM 输出。
   - 阶段 3：根据指标逐步扩大覆盖面，最终默认启用。
3. **回滚方案**
   - 任意阶段可通过 Redis 动态配置关闭 LLM 分类。
   - 保留启发式逻辑，确保关闭后策略不会出现空场景。

## 4. 风险与缓解
| 风险 | 描述 | 缓解措施 |
| ---- | ---- | -------- |
| 延迟增加 | 每次查询多一次 LLM 调用 | 启用条件过滤、缓存、并发限流、使用轻量模型 |
| 成本上升 | 分类调用按量计费 | 设定预算警报、将长查询或高价值查询优先级划分、采用 cheaper 模型 |
| Prompt 注入 | 用户输入可能诱导模型输出非法结构 | 约束输入长度、使用 JSON schema、加入后端校验 |
| 误判影响检索 | 错误标签导致召回不足或上下文冗余 | 设置置信度阈值与回退、持续评估样本、提供人工标注反馈通道 |

## 5. 时间线建议
1. **Week 1**：数据收集与标注、Prompt 设计。
2. **Week 2**：模块开发、单元测试、基础监控。
3. **Week 3**：离线评估 + Shadow 模式部署。
4. **Week 4**：灰度上线、根据指标调优、准备正式切换。

## 6. 下一步
- 确认预算与调用 QPS 上限。
- 指派数据标注与 Prompt 设计负责人。
- 根据阶段计划投入开发，并纳入迭代排期。

