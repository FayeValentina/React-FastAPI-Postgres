# 本地大模型 + RAG 最终实施指南

> 目标：在现有微服务架构中，引入 `llama.cpp` OpenAI 兼容服务器和基于 PostgreSQL + pgvector 的检索增强生成（RAG）。请先完成本指南前半部分的本地 LLM 部署，再继续实施 RAG。两部分修改均需合并到现有 `docker-compose.*.yml` 文件中，注意不要互相覆盖。

---

## 1. 关键注意事项
- **网络配置**：新增的 `llm_init` 与 `llama_server` 服务必须加入现有 `dbNetWork` 网络，确保 `backend` 能解析其服务名。
- **模型仓库路径**：在设置 `HF_REPO_ID`、`HF_FILENAME` 前务必到 Hugging Face 核实仓库与文件名，避免下载失败。
- **Compose 合并**：`LLM` 和 `RAG` 都会修改 `docker-compose.*.yml`。请在前者基础上追加后者的内容，不要互相覆盖。
- **首次调用延迟**：`llama_server` 启动后仍需数秒~数十秒将模型加载到内存，首次请求可能较慢。

---

## 2. 环境变量
在 `.env.dev` 与 `.env.prod` 中新增/合并以下变量（敏感信息勿提交仓库）：

```bash
# llama_server 接入参数
LLM_BASE_URL=http://llama_server:8080/v1
LLM_API_KEY=sk-local

# Hugging Face 模型下载（确认仓库路径）
HF_TOKEN=xxx_your_hf_token_xxx
HF_REPO_ID=google/gemma-3-4b-it-qat-q4_0-gguf   # 请核实真实路径
HF_FILENAME=gemma-3-4b-it-q4_0.gguf
HF_REVISION=main

# llama_server 使用的模型名（默认与 HF_FILENAME 相同）
LLM_MODEL=${HF_FILENAME}

# RAG 设置
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
RAG_TOP_K=3
```

> 提示：可在后端 `Settings` 中让 `LLM_MODEL` 默认读取 `HF_FILENAME`，减少手动同步。

---

## 3. 后端依赖安装
在 `backend/pyproject.toml` 的 `[tool.poetry.dependencies]` 中确保存在：

```toml
openai = "^1.40.0"
sentence-transformers = "^3.0.1"
pgvector = "^0.2.5"
nltk = "^3.9"
```

安装并下载分词器数据：

```bash
cd backend
poetry lock
poetry install
poetry run python -c "import nltk; nltk.download('punkt')"
```

---

## 4. Docker Compose 修改
### 新增命名卷与 LLM 服务
在 `docker-compose.dev.yml` 和 `docker-compose.prod.yml` 中添加：

```yaml
volumes:
  models_data: {}

services:
  llm_init:
    image: python:3.11-slim
    environment:
      - HF_TOKEN=${HF_TOKEN}
      - HF_REPO_ID=${HF_REPO_ID}
      - HF_FILENAME=${HF_FILENAME}
      - HF_REVISION=${HF_REVISION:-main}
      - PIP_NO_CACHE_DIR=1
    command: >-
      sh -lc "set -euo pipefail;\
      python -m pip install -q 'huggingface_hub[hf_xet]';\
      python - <<'PY'\
from huggingface_hub import hf_hub_download
import os, shutil
repo=os.environ['HF_REPO_ID']
fn=os.environ['HF_FILENAME']
rev=os.environ.get('HF_REVISION','main')
token=os.environ.get('HF_TOKEN')
path = hf_hub_download(repo_id=repo, filename=fn, revision=rev, token=token)
os.makedirs('/models', exist_ok=True)
dst=f'/models/{fn}'
if os.path.abspath(path)!=os.path.abspath(dst):
    shutil.copy2(path, dst)
print('Downloaded:', dst)
PY\
      ls -lh /models;"
    volumes:
      - models_data:/models
    networks:
      - dbNetWork
    restart: "no"

  llama_server:
    image: ghcr.io/ggerganov/llama.cpp:server
    depends_on:
      llm_init:
        condition: service_completed_successfully
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1:8080/v1/models >/dev/null 2>&1 || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 6
      start_period: 15s
    command:
      - --model
      - /models/${HF_FILENAME}
      - --port
      - "8080"
      - --host
      - 0.0.0.0
      - --ctx-size
      - "8192"
      - --parallel
      - "2"
      - --api-key
      - ${LLM_API_KEY}
    volumes:
      - models_data:/models:ro
    networks:
      - dbNetWork
```

### PostgreSQL 替换为 pgvector 镜像
将 `postgres` 服务镜像改为稳定版：

```yaml
postgres:
  image: pgvector/pgvector:pg16
  # 其余配置保持不变
```

### 后端环境变量透传
在 `backend` 服务中追加：

```yaml
- EMBEDDING_MODEL=${EMBEDDING_MODEL}
- RAG_TOP_K=${RAG_TOP_K:-3}
```

> 修改后执行 `docker compose up -d --build`，确保所有服务重建并加入 `dbNetWork`。

---

## 5. 预下载模型并启动
```bash
docker compose run --rm llm_init      # 下载模型到命名卷
docker compose up -d                  # 启动所有服务
```

---

## 6. 数据库迁移：知识库表
```bash
docker compose exec backend alembic revision -m "add knowledge table" --autogenerate
```
编辑生成的迁移文件（`down_revision` 由 Alembic 自动填写，不要复制示例中的占位值），示例：

```python
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = 'xxxx'
down_revision = '上一版本号'

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.create_table(
        'knowledge_chunks',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('source', sa.String, nullable=True),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('embedding', Vector(dim=384), nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('now()')),
    )
    op.create_index(
        'ix_knowledge_chunks_embedding',
        'knowledge_chunks',
        ['embedding'],
        postgresql_using='ivfflat',
        postgresql_with={'lists': 100},
    )

def downgrade() -> None:
    op.drop_index('ix_knowledge_chunks_embedding', table_name='knowledge_chunks')
    op.drop_table('knowledge_chunks')
```

运行迁移：
```bash
docker compose exec backend alembic upgrade head
```

---

## 7. 后端代码要点
- **设置**：通过 Pydantic Settings 读取上述环境变量，`LLM_MODEL` 可默认取 `HF_FILENAME`。
- **WS 聊天**：在已有的 `app/api/v1/endpoints/llm_ws.py` 中整合检索逻辑，而不是新建文件。收到用户消息后：
  1. 调用 `search_similar_chunks` 检索相似文本。
  2. 将返回的上下文与问题拼成 Prompt，设置较低 `temperature` 调用 `llama_server`。
  3. 保持原有流式返回实现。
- **服务层**：在 `app/modules/knowledge_base/service.py` 中实现 `add_document_to_knowledge_base` 和 `search_similar_chunks` 等函数。

---

## 8. 前端 Chat 页面
- 通过 WebSocket 与后端交互：`const url = (import.meta.env.VITE_API_URL || '').replace(/^http/, 'ws') + '/ws/llm'`
- 在复杂部署（子路径、端口）下请验证 URL 生成是否正确。
- 首次请求可能因模型加载而等待较长时间，属于正常现象。

---

## 9. 运行与验证
1. 重新构建并启动：`docker compose up -d --build`
2. 添加文档至知识库：
   ```bash
   curl -X POST http://localhost/api/v1/knowledge/add-document \
     -H "Content-Type: application/json" \
     -d '{"source":"README","content":"...任意文本..."}'
   ```
3. 打开前端聊天页面测试：
   - 提问与文档相关的问题应返回基于上下文的答案。
   - 提问无关问题应提示“资料不足”。

---

## 10. 常见问题
- **下载失败**：确认 `HF_REPO_ID` 与 `HF_FILENAME` 是否正确、`HF_TOKEN` 是否有权限。
- **网络不通**：确认 `llm_init`、`llama_server`、`backend` 均加入 `dbNetWork`。
- **迁移失败**：确保使用 Alembic 自动生成的 `down_revision`，并已替换 PostgreSQL 镜像。
- **分词器下载卡住**：使用 `python -c "import nltk; nltk.download('punkt')"` 代替 `nltk.downloader` GUI。

---

通过以上步骤，即可在本项目中完成轻量本地大模型部署及 RAG 功能的集成。
