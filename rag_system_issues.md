# RAG 系统问题清单

## 1. 接口层参数覆盖
- **动态配置强制回落到 3 条结果**：REST 与 WebSocket 检索入口都会把策略结果里的 `RAG_TOP_K` 当作最终 top-k，忽略调用方请求体提供的值。由于默认动态配置把 `RAG_TOP_K` 设为 3，且策略在 `default` 场景不会提升该值，即便客户端携带 `top_k=5` 也只会收到 3 条结果。长远来看，这会让“前端调节返回条数”失效。建议：优先使用用户请求值，在策略给出更大值时再取 `max(user, strategy)`，或把策略的 top-k 作为上限而非硬覆盖。【F:backend/app/api/v1/endpoints/knowledge.py†L152-L179】【F:backend/app/api/v1/endpoints/llm_ws.py†L80-L107】【F:backend/app/core/config.py†L323-L356】

## 2. 检索服务（`backend/app/modules/knowledge_base/service.py`）
- **重排候选上限未生效**：`baseline_filtered` 直接复制粗排后所有候选并送入交叉编码器，没有按照 `RAG_RERANK_CANDIDATES` 截断，导致延迟和算力成本完全取决于向量召回的上限。建议在进入重排前先对 `filtered` 排序后截断到策略指定数量，再送入模型。【F:backend/app/modules/knowledge_base/service.py†L456-L487】
- **语言加分在重排后被抹掉**：粗排阶段为同语种片段叠加 `RAG_SAME_LANG_BONUS`，但重排阶段把 `item.score` 覆盖为交叉编码器的概率，未重新补回语言偏置，导致多语环境下策略调参失效。建议在重排完成后重新加回语言 bonus 或单独存储粗排得分用于最终排序。【F:backend/app/modules/knowledge_base/service.py†L429-L435】【F:backend/app/modules/knowledge_base/service.py†L479-L481】
- **MMR 去冗得分未用于最终排序**：`_mmr_select` 会计算 `mmr_score`，但选出的结果在返回前又按 `(score, similarity)` 排序，等于丢掉了多样性信号。建议把 `mmr_score` 纳入排序键，或干脆保持 MMR 选出的顺序。【F:backend/app/modules/knowledge_base/service.py†L521-L529】
- **重排阈值仍作为硬筛**：重排后会立即用 `rerank_score_threshold` 过滤，阈值一旦偏高就会把候选清空，与策略希望的“多召回，再由预算裁剪”冲突。建议改成仅用于日志或权重调整，把真正的裁剪交给 MMR 和上下文预算。【F:backend/app/modules/knowledge_base/service.py†L483-L487】
- **交叉编码器只看前 512 字符**：长段落只截取首 512 字符作为重排输入，若关键信息位于后半段会被忽略。建议在入库阶段生成摘要字段、或在重排阶段按句子边界截取而非硬切。【F:backend/app/modules/knowledge_base/service.py†L461-L463】

## 3. 策略层（`backend/app/modules/knowledge_base/strategy.py`）
- **精确场景的阈值偏高**：`precise` 场景把 `RAG_RERANK_SCORE_THRESHOLD` 提升到 ≥0.6，而服务层又对该阈值做硬筛，导致可用候选骤减甚至归零。建议把高阈值换成较低的排序权重，或在服务层改为软约束。【F:backend/app/modules/knowledge_base/strategy.py†L180-L209】
- **文档聚焦场景放大重排候选**：`document_focus` 场景把 `RAG_RERANK_CANDIDATES` 拉到至少 120，与当前服务层“全部送入重排”的行为叠加，会显著拖慢响应。建议配合第 2 点修复，在服务层截断，或在策略端把值与 `RAG_MAX_CANDIDATES` 联动保持在可控范围。【F:backend/app/modules/knowledge_base/strategy.py†L200-L205】

## 4. 文档抽取与切分
- **未利用 unstructured 提供的语言信息**：抽取阶段虽然为 `ExtractedElement` 预留了 `language` 字段，但 `_element_to_payload` 并未把 `element.metadata` 里的语言信号写入，后续切分只能再次调用 `detect_language`。建议在提取时尝试读取 `metadata.language` 或 `metadata.languages` 并写入 `ExtractedElement.language`，减少重复检测。【F:backend/app/modules/knowledge_base/ingest_extractor.py†L14-L41】
- **语言检测日志过于喧闹**：`detect_language` 及其辅助函数在每次调用时都会输出多条 INFO 日志，而 `split_elements` 会对每个 Markdown section 和子片段重复检测，批量导入时日志量巨大并拖慢 I/O。建议把这些日志降到 DEBUG，并为切分阶段提供语言缓存，避免同一段文本多次检测。【F:backend/app/modules/knowledge_base/ingest_language.py†L39-L155】【F:backend/app/modules/knowledge_base/ingest_splitter.py†L232-L259】
- **切分阶段未复用上游语言判定**：即使 `ExtractedElement` 带有 `language`，`split_elements` 仍会对 Markdown 小节再次调用 `detect_language`，导致同一段文本多次耗时检测。建议优先使用 `element.language`，仅在缺失时再调用检测器，同时对 `_markdown_sections` 输出做缓存或批量检测。【F:backend/app/modules/knowledge_base/ingest_splitter.py†L232-L255】

## 5. 已复核无问题的结论
- **上下文预算已在 Prompt 构造层生效**：先前审计担心 `RAG_CONTEXT_TOKEN_BUDGET` / `RAG_CONTEXT_MAX_EVIDENCE` 未落实，但 `_build_context` 会严格按照这两个配置截断证据，因此无需在检索层重复裁剪。此项已复核，无需改动。【F:backend/app/modules/llm/service.py†L58-L118】
