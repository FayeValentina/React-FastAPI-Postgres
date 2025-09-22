# 知识库模块重构指南

1. 现行架构分析
   - 文档清洗：`backend/app/modules/knowledge_base/service.py` 中 `_strip_markdown_sync` 依赖 `markdown` + `BeautifulSoup` 仅覆盖纯文本/Markdown；编码探测通过 `_decode_bytes_to_text` 手工尝试多种 codec。
   - 分句与分块：`_segment_sentences`、`_pack_sentences`、`_estimate_tokens` 基于自研规则（spaCy + 正则 + 估算 token），并额外维护代码块分割 `_split_code_block` 和语言检测 `_detect_language`。
   - 入库流程：`ingest_document_content`、`ingest_document_file` 负责清洗 → 分块 → SentenceTransformer 向量化 → `crud_knowledge_base.bulk_create_document_chunks` 写入，依赖动态配置控制 chunk 大小与重叠比。
   - 检索层：沿用 pgvector + `_mmr_select` 做 MMR 去冗，暂不调整。

2. 重构流程
  a. 安装相关依赖
      - 在 `backend/pyproject.toml` 的 `[tool.poetry.dependencies]` 中新增：
        ```toml
        unstructured = "^0.17.0"
        charset-normalizer = "^3.3"
        langchain-text-splitters = "^0.3.0"
        tiktoken = "^0.7"
        lingua-language-detector = { version = "^1.4", optional = true }
        ```
      - 如需启用 `lingua-language-detector` 可选依赖，请在 `backend/pyproject.toml` 的 `[tool.poetry.extras]` 中增加相应分组（例如 `language-detectors = ["lingua-language-detector"]`），并在部署或安装时显式执行 `poetry install --with language-detectors`，避免遗漏该包。
      - 若未来扩展到 PDF、Office 等格式，可再引入 `pypdf`、`python-docx` 等解析插件；届时同样需记录进 `pyproject.toml` 并更新锁文件。
      - 当前只处理纯文本/Markdown 文档，部署镜像无需额外安装 `poppler-utils`、`libreoffice` 等系统依赖。如未来扩展到 PDF、Office 等格式，再在 `backend/Dockerfile` 与 `backend/Dockerfile.prod` 中追加相应包。

   b. 配置与环境调整
      - 若需新增动态参数（例如 `RAG_USE_LINGUA`、新的 chunk 大小/重叠数值），参照：
        - `backend/app/core/config.py`（后端默认配置）
        - `backend/app/modules/admin_settings/schemas.py`（动态设置 Schema）
        - `frontend/src/types/adminSettings.ts` 与 `frontend/src/components/AdminSettings/settingDefinitions.ts`（管理端展示与编辑）
      - 新参数需同时补齐以下位置的默认值或映射：
        - `backend/app/core/config.py` 中 `Settings` 字段定义及 `dynamic_settings_defaults()` 返回值。
        - `backend/app/infrastructure/dynamic_settings/service.py` 若有基于默认值的拷贝逻辑（目前会透传 `settings.dynamic_settings_defaults()`）。
        - 前端类型 `frontend/src/types/adminSettings.ts` 的 `AdminSettingKey` 联合类型，以及 `frontend/src/components/AdminSettings/settingDefinitions.ts` 的表单定义。
        - 任何依赖默认配置的测试，如 `backend/app/tests/infrastructure/test_dynamic_settings_service.py`、`backend/app/tests/api/test_admin_settings.py`，需更新期望值。
      - 保持新增字段的命名、校验与描述方式与现有动态设置一致，并为前端提供默认值与表单规则。
      - 容器或 CI 脚本中增加对应依赖的安装步骤，确保测试环境与生产环境一致。

   c. 代码重构步骤
      - 模块拆分：在 `backend/app/modules/knowledge_base/` 下新增模块，例如：
        - `ingest_extractor.py`：负责 `unstructured` 抽取与编码探测兜底。
        - `ingest_splitter.py`：封装 `MarkdownHeaderTextSplitter`、`RecursiveCharacterTextSplitter`、`TokenTextSplitter` 的组合逻辑与语言标注。
        - `ingest_language.py`：集中语言检测（`lingua` + 正则回退）。
        - 其他按需的辅助模块（如 `ingest_settings.py` 按动态参数解析）。
      - `service.py` 精简为仅保留被 `backend/app/api/v1/endpoints/knowledge.py` 与 `backend/app/api/v1/endpoints/llm_ws.py` 直接调用的接口函数（如 `ingest_document_file`、`ingest_document_content`、检索相关函数），在函数内部直接从新模块导入实现：例如 `from app.modules.knowledge_base.ingest_extractor import extract_document_elements`；无需额外的 `__init__.py` 导出。
      - 抽取阶段：使用 `unstructured.partition.auto.partition` 解析文件；若失败，回退到 `charset-normalizer` 解码的纯文本方式，并将元素元数据传递给下游。
      - 切分阶段：采用第三方 splitters 取代 `_segment_sentences`、`_pack_sentences`、`_split_code_block`、`_estimate_tokens`，必要时在 splitter 输出中标记代码块语言。
      - 语言检测：优先使用 `lingua`，无法使用时回退到轻量正则；删除 `langdetect` 依赖及相关代码。
      - 入库流程：在新的 ingest 模块中完成读取 → 分块 → 向量化 → `bulk_create_document_chunks`，并保持 overwrite 逻辑和事务处理不变；根据需要扩展 payload 以保存 `unstructured` 元数据。
      - 清理旧逻辑：删除 `_allowed_text_mime`、`_allowed_text_suffix` 等不再使用的函数；若仍需防毒，改为基于解析结果或文件大小的检查。

   d. 测试与验证
      - 单元测试：在 `backend/app/tests/` 中为抽取、分块、语言标注编写新测试，覆盖 Markdown 标题拆分、代码块保留、CJK 文本处理等场景。
      - 集成测试：通过容器环境运行，例如先启动开发编排 `docker compose -f docker-compose.dev.yml up backend db`，再在容器内执行 `docker compose exec backend bash -lc "poetry run pytest --cov=app"`；同时通过管理端或 API 上传 Markdown/纯文本进行手工验证，确认 chunk 数量与 metadata。
      - 回归检查：在 Docker 容器内测试 `ingest_document_file` 的覆盖写入流程，确认不会产生重复数据，向量维度与旧模型一致。

3. 风险与回滚
   - `unstructured` 体积较大，初次加载耗时，须在生产环境测量冷启动与镜像大小。
   - OCR 或额外格式支持可能需要系统依赖，如部署失败需可快速回滚到旧抽取模块（可将旧逻辑迁至 `legacy/` 模块备用）。
   - Splitter 参数配置不当会导致 chunk 过长或过多，上线前需针对样本文档评估 chunk 分布。

4. 后续优化建议
   - 按需引入近重复检测（MinHash/SimHash）减少库内冗余。
   - 若未来接入外部向量库，可借助 LangChain VectorStore 提供的 MMR/过滤能力替换 `_mmr_select`。
   - 利用动态配置面板支持在线调整 chunk 大小、重叠比例、语言检测开关，方便不同数据集快速调优。
