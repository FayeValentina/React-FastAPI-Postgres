# 本地大模型 + RAG 一体化实施指南（最终版）

> 目标：在现有微服务架构中，一次性完成 **本地 LLM（llama.cpp + GGUF，OpenAI 兼容 API）** 与 **RAG（PostgreSQL + pgvector）** 的集成。本文档既包含完整步骤，也涵盖关键注意事项与调优建议，适配本地开发与生产（OCI ARM）两套 Compose。

---

## 目录

1. 背景与总览
2. 前置条件与资源
3. 环境变量（统一清单）
4. Docker Compose 修改（统一版）
5. 后端依赖安装与配置
6. 数据库迁移：知识库表（pgvector + 余弦索引）
7. 后端实现要点（OpenAI SDK + WebSocket + RAG）
8. 前端 Chat 页面（WebSocket 直连后端）
9. Nginx 反代与 WS 透传
10. 启动顺序与验证
11. 更换/升级模型流程
12. 调优与运维建议（A1 机器）
13. 常见问题排查（FAQ）
14. 附：一键验证命令

---

## 1) 背景与总览

* 形态：独立容器 `llama_server`（OpenAI 兼容 HTTP），不嵌入后端进程。
* 数据：命名卷 `models_data` 用于持久化 GGUF 模型文件。
* 预热：`llm_init` 一次性下载模型至卷；`llama_server` 以只读挂载使用。
* 调用：后端以 **OpenAI Python SDK** 调用 `http://llama_server:8080/v1`；前端通过 **WebSocket** 与后端交互（流式）。
* RAG：在 `backend` 内实现向量化、检索与 Prompt 组装，数据库使用 **PostgreSQL + pgvector**。
* 网络：`llm_init`、`llama_server`、`backend` 加入同一 Compose 网络（示例名：`dbNetWork`）。

调用链：**Frontend → WebSocket → Backend（OpenAI SDK）→ llama\_server → Backend → Frontend（stream）**

---

## 2) 前置条件与资源

* 机器：OCI ARM（`VM.Standard.A1.Flex`，建议 4 OCPU / 24GB RAM / 120GB+ 磁盘）。
* Docker/Compose：Docker Engine + Docker Compose v2（建议 ≥ v2.20）。
* 模型：如 `google/gemma-3-4b-it-gguf` 下的 `gemma-3-4b-it-q4_0.gguf`（约 3GB）。
* 账号与权限：Hugging Face 账号、同意许可、有效 `HF_TOKEN`（如仓库为 gated）。

---

## 3) 环境变量（统一清单）

将以下变量加入 `.env.dev` / `.env.prod`（**敏感信息勿提交仓库**）：

```bash
# LLM 接入
LLM_BASE_URL=http://llama_server:8080/v1
LLM_API_KEY=sk-local

# Hugging Face 模型下载（先核对真实路径与文件名）
HF_TOKEN=xxx_your_hf_token_xxx
HF_REPO_ID=google/gemma-3-4b-it-gguf
HF_FILENAME=gemma-3-4b-it-q4_0.gguf
HF_REVISION=main
HF_HUB_ENABLE_HF_TRANSFER=1   # 启用 hf_transfer 加速

# LLM 模型名（默认与 HF_FILENAME 相同）
LLM_MODEL=${HF_FILENAME}

# RAG 设置（384 维示例模型）
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
RAG_TOP_K=3
```

> 提示：`LLM_MODEL` 可在后端 Settings 中默认读取 `HF_FILENAME`，减少变量不同步。

---

## 4) Docker Compose 修改（统一版）

在 `docker-compose.dev.yml` 与 `docker-compose.prod.yml` 中**增量合并**以下片段：

```yaml
volumes:
  models_data: {}

services:
  # 1) 预下载模型（一次性执行，完成即退出）
  llm_init:
    image: python:3.11-slim
    networks:
      - dbNetWork
    environment:
      - HF_TOKEN=${HF_TOKEN}
      - HF_REPO_ID=${HF_REPO_ID}
      - HF_FILENAME=${HF_FILENAME}
      - HF_REVISION=${HF_REVISION:-main}
      - PIP_NO_CACHE_DIR=1
      - HF_HUB_ENABLE_HF_TRANSFER=1
    command: |
      sh -lc '
        set -euo pipefail
        python -m pip install -q "huggingface_hub[hf_transfer]"
        python - <<'"'"'PY'"'"'
from huggingface_hub import hf_hub_download
import os, shutil
repo = os.environ["HF_REPO_ID"]
fn = os.environ["HF_FILENAME"]
rev = os.environ.get("HF_REVISION", "main")
token = os.environ.get("HF_TOKEN")
path = hf_hub_download(repo_id=repo, filename=fn, revision=rev, token=token)
os.makedirs("/models", exist_ok=True)
dst = f"/models/{fn}"
if os.path.abspath(path) != os.path.abspath(dst):
    shutil.copy2(path, dst)
print("Downloaded:", dst)
PY
        ls -lh /models
      '
    volumes:
      - models_data:/models
    restart: "no"

  # 2) OpenAI 兼容的 llama.cpp 服务器
  llama_server:
    image: ghcr.io/ggerganov/llama.cpp:server
    networks:
      - dbNetWork
    depends_on:
      llm_init:
        condition: service_completed_successfully
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://127.0.0.1:8080/v1/models >/dev/null || exit 1"]
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
      # 可选：- --log-disable
    expose:
      - "8080"
    volumes:
      - models_data:/models:ro
    restart: unless-stopped

  # 3) PostgreSQL（pgvector 版）
  postgres:
    image: pgvector/pgvector:pg16
    # 其余端口、卷、环境变量与现有配置一致

  # 4) 让 backend 能够调用本地 LLM，并透传 RAG 变量
  backend:
    # ... 你现有的镜像/构建配置 ...
    environment:
      - LLM_BASE_URL=${LLM_BASE_URL}
      - LLM_API_KEY=${LLM_API_KEY}
      - EMBEDDING_MODEL=${EMBEDDING_MODEL}
      - RAG_TOP_K=${RAG_TOP_K:-3}
    depends_on:
      llama_server:
        condition: service_healthy
    # 其余保持不变
```

> 说明：`llama_server` 只 `expose` 内部端口，不对外映射；`backend` 与其同网可通过服务名访问。

---

## 5) 后端依赖安装与配置

`backend/pyproject.toml` 的依赖确保包含：

```toml
openai = "^1.40.0"
sentence-transformers = "^3.0.1"
pgvector = "^0.2.5"
nltk = "^3.9"
```

安装并下载分词器：

```bash
cd backend
poetry lock && poetry install
poetry run python -c "import nltk; nltk.download('punkt')"
```

> A1（aarch64）拉取 `torch` 较慢、镜像体积较大，可考虑轻量模型（仍需同步维度，见下文）。

---

## 6) 数据库迁移：知识库表（pgvector + 余弦索引）

创建迁移并将索引 **显式指定 opclass** 为 `vector_cosine_ops`，并在迁移末尾执行 `ANALYZE`：

```python
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = 'xxxx'
down_revision = '<previous_revision>'

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.create_table(
        'knowledge_chunks',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('source', sa.String, nullable=True, comment='来源标识'),
        sa.Column('content', sa.Text, nullable=False, comment='文本内容'),
        sa.Column('embedding', Vector(dim=384), nullable=False, comment='向量表示'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('now()')),
    )
    op.create_index(
        'ix_knowledge_chunks_embedding',
        'knowledge_chunks',
        ['embedding'],
        postgresql_using='ivfflat',
        postgresql_with={'lists': 100},
        postgresql_ops={'embedding': 'vector_cosine_ops'},
    )
    op.execute("ANALYZE knowledge_chunks;")

def downgrade() -> None:
    op.drop_index('ix_knowledge_chunks_embedding', table_name='knowledge_chunks')
    op.drop_table('knowledge_chunks')
    op.execute("DROP EXTENSION IF EXISTS vector;")
```

> 如更换嵌入模型（例如 `gte-small`，维度 384/768 等），需同步修改 `Vector(dim=…)`。

---

## 7) 后端实现要点（OpenAI SDK + WebSocket + RAG）

### 7.1 Settings

```python
# app/core/settings.py
import os
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    LLM_BASE_URL: str = "http://llama_server:8080/v1"
    LLM_API_KEY: str = "sk-local"
    LLM_MODEL: str = Field(default_factory=lambda: os.getenv("HF_FILENAME", "gemma-3-4b-it-q4_0.gguf"))
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", 3))

settings = Settings()
```

### 7.2 OpenAI 客户端

```python
# app/modules/llm/client.py
from openai import OpenAI
from app.core.settings import settings

client = OpenAI(base_url=settings.LLM_BASE_URL, api_key=settings.LLM_API_KEY)
```

### 7.3 WebSocket（流式）

```python
# app/api/v1/endpoints/llm_ws.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.modules.llm.client import client
from app.core.settings import settings
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.database.postgres_base import get_async_session
from app.modules.knowledge_base.service import search_similar_chunks

router = APIRouter(prefix="/ws", tags=["llm"])

@router.websocket("/chat")
async def ws_chat(ws: WebSocket, db: AsyncSession = Depends(get_async_session)):
    await ws.accept()
    history = []
    try:
        while True:
            incoming = await ws.receive_json()
            if incoming.get("type") == "reset":
                history.clear(); await ws.send_json({"type": "reset_ok"}); continue

            user_text = (incoming.get("content") or "").strip()
            if not user_text:
                await ws.send_json({"type": "error", "message": "empty content"}); continue

            # 检索增强
            similar = await search_similar_chunks(db, user_text, settings.RAG_TOP_K)
            context = "
---
".join(c.content for c in similar)
            system_prompt = "You are a helpful assistant."
            if context:
                user_text = f"请参考以下资料回答问题，若资料不足请说明：
{context}
问题：{user_text}"

            history.append({"role": "user", "content": user_text})

            stream = client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[{"role": "system", "content": system_prompt}] + history,
                stream=True,
                temperature=0.2,
            )

            acc = []
            for chunk in stream:
                delta = chunk.choices[0].delta
                token = getattr(delta, "content", None) or (delta.get("content") if isinstance(delta, dict) else None)
                if token:
                    acc.append(token)
                    await ws.send_json({"type": "delta", "content": token})

            text = "".join(acc)
            history.append({"role": "assistant", "content": text})
            await ws.send_json({"type": "done"})

    except WebSocketDisconnect:
        pass
```

### 7.4 知识库服务（分块/向量化/检索）

```python
# app/modules/knowledge_base/service.py
from sentence_transformers import SentenceTransformer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pgvector.sqlalchemy import cosine_distance
from . import models
from app.core.settings import settings

_model = SentenceTransformer(settings.EMBEDDING_MODEL)

def split_text(content: str, target: int = 300, overlap: int = 50) -> list[str]:
    """最小可用的按句分块，块大小约 target 字符，块间 overlap 字符重叠。
    依赖 nltk.sent_tokenize（已在依赖中声明并在部署步骤下载 punkt）。
    """
    try:
        from nltk.tokenize import sent_tokenize
        sentences = sent_tokenize(content or "")
    except Exception:
        # 回退：按句号/换行粗略切分，避免因 NLTK 数据缺失而报错
        import re
        sentences = [s.strip() for s in re.split(r"[。.!?\n]+", content or "") if s.strip()]

    chunks: list[str] = []
    cur = ""
    for s in sentences:
        if not s:
            continue
        if not cur:
            cur = s
            continue
        sep = " " if not cur.endswith((" ", "\n")) else ""
        if len(cur) + len(sep) + len(s) <= target:
            cur = f"{cur}{sep}{s}"
        else:
            # 结束当前块
            chunks.append(cur)
            # 下一块以 overlap 个字符作为前缀
            prefix = cur[-overlap:] if overlap > 0 and len(cur) > overlap else ""
            sep2 = " " if prefix and not prefix.endswith((" ", "\n")) else ""
            cur = f"{prefix}{sep2}{s}" if prefix else s
    if cur:
        chunks.append(cur)
    return chunks or ([content] if content else [])

async def add_document_to_knowledge_base(db: AsyncSession, source: str, content: str) -> int:
    chunks = split_text(content)
    vectors = _model.encode(chunks, normalize_embeddings=True)
    for c, v in zip(chunks, vectors):
        db.add(models.KnowledgeChunk(source=source, content=c, embedding=v))
    await db.commit()
    return len(chunks)

async def search_similar_chunks(db: AsyncSession, query: str, top_k: int):
    q_emb = _model.encode([query], normalize_embeddings=True)[0]
    stmt = (
        select(models.KnowledgeChunk)
        .order_by(cosine_distance(models.KnowledgeChunk.embedding, q_emb))
        .limit(top_k)
    )
    result = await db.scalars(stmt)
    return result.all()
```

> 注意：首次加载嵌入模型时会较慢，可在应用启动时预热。

### 7.5 文档入库 API

```python
# app/api/v1/endpoints/knowledge.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.database.postgres_base import get_async_session
from app.modules.knowledge_base.service import add_document_to_knowledge_base

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

class DocumentCreate(BaseModel):
    source: str
    content: str

@router.post("/add-document", status_code=201)
async def add_document(doc: DocumentCreate, db: AsyncSession = Depends(get_async_session)):
    count = await add_document_to_knowledge_base(db, doc.source, doc.content)
    return {"message": f"文档已添加并切分为 {count} 块"}
```

挂载路由（示例）：

```python
# app/api/v1/router.py（或你的主路由聚合处）
from fastapi import APIRouter
from app.api.v1.endpoints import knowledge

api_router = APIRouter()
api_router.include_router(knowledge.router)
```

---

## 8) 前端 Chat 页面（WebSocket 直连后端）

以 Vite + React + TS 为例（简化示意）：

```tsx
// src/pages/Chat.tsx
import { useEffect, useRef, useState } from 'react'
const WS_URL = (import.meta.env.VITE_API_URL || '').replace(/^http/, 'ws') + '/api/v1/ws/chat'
export default function Chat() {
  const wsRef = useRef<WebSocket | null>(null)
  const [messages, setMessages] = useState<{role:'user'|'assistant', content:string}[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  useEffect(() => {
    const ws = new WebSocket(WS_URL)
    wsRef.current = ws
    ws.onmessage = (ev) => {
      const data = JSON.parse(ev.data)
      if (data.type === 'delta') {
        setMessages((prev) => {
          const last = prev[prev.length - 1]
          if (last && last.role === 'assistant') {
            const copy = prev.slice()
            copy[copy.length - 1] = { role: 'assistant', content: last.content + data.content }
            return copy
          }
          return [...prev, { role: 'assistant', content: data.content }]
        })
      } else if (data.type === 'done') {
        setLoading(false)
      }
    }
    ws.onclose = () => {}
    return () => ws.close()
  }, [])
  const send = () => {
    const text = input.trim()
    if (!text || !wsRef.current) return
    setMessages((m) => [...m, { role: 'user', content: text }])
    setMessages((m) => [...m, { role: 'assistant', content: '' }])
    setLoading(true)
    wsRef.current.send(JSON.stringify({ content: text }))
    setInput('')
  }
  return (
    <div style={{ maxWidth: 720, margin: '0 auto', padding: 16 }}>
      <h2>Local LLM Chat</h2>
      <div style={{ border: '1px solid #ddd', padding: 12, minHeight: 320 }}>
        {messages.map((m, i) => (
          <div key={i} style={{ whiteSpace: 'pre-wrap', margin: '8px 0' }}>
            <strong>{m.role}:</strong> {m.content}
          </div>
        ))}
        {loading && <div>Assistant is typing…</div>}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <input value={input} onChange={(e) => setInput(e.target.value)} style={{ flex: 1 }} />
        <button onClick={send} disabled={loading}>Send</button>
      </div>
    </div>
  )
}
```

---

## 9) Nginx 反代与 WS 透传

`llama_server` 不对外暴露；后端已在内部访问。若后端新增 WS 端点，Nginx 需透传：

```nginx
location /api/ {
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 600s;
    proxy_send_timeout 600s;
    proxy_pass http://backend:8000;  # 依据你的 upstream
}
```

---

## 10) 启动顺序与验证

1. **预下载模型**：`docker compose run --rm llm_init`
2. **启动所有服务**：`docker compose up -d --build`
3. **验证 LLM**（在 backend 容器内）：

   * `curl -s -H 'Authorization: Bearer ${LLM_API_KEY}' http://llama_server:8080/v1/models`
   * 调用对话接口见「附：一键验证命令」。
4. **数据库迁移**：`alembic upgrade head`
5. **知识入库**：调用 `/api/v1/knowledge/add-document` 接口写入测试文本。
6. **前端验证**：打开 Chat 页面，测试一般对话与基于资料的回答。

---

## 11) 更换/升级模型流程

1. 修改 `.env.*` 中 `HF_REPO_ID` / `HF_FILENAME` / `HF_REVISION`。
2. 运行：`docker compose run --rm llm_init`（下载新模型至同一卷）。
3. 重启：`docker compose up -d llama_server`（或整体重启）。

---

## 12) 调优与运维建议（A1 机器）

* 首选参数：`--ctx-size 8192`、`--parallel 2`；如 OOM 或加载慢，降至 `4096`、`1`。
* 量化：q4\_0 → q3\_k\_m 可进一步省内存；吞吐/质量按需权衡。
* 监控：观察 `llama_server` 日志中的 KV-Cache 与吞吐；必要时限流与超时。

---

## 13) 常见问题排查（FAQ）

* **下载 401/403**：检查 `HF_TOKEN` 权限；`HF_REPO_ID`/`HF_FILENAME` 是否拼写正确；已开启 `HF_HUB_ENABLE_HF_TRANSFER`。
* **健康检查失败**：确认卷内 `.gguf` 文件与路径；改用 `curl -fsS`；延长 `start_period`。
* **WS 不通**：Nginx 是否透传 `Upgrade`/`Connection`；反代超时是否过短。
* **迁移/检索异常**：确认使用 `pgvector/pgvector:pg16`；索引使用 `vector_cosine_ops`；维度与嵌入模型匹配；执行过 `ANALYZE`。
* **ARM 镜像过大**：更换更轻嵌入模型或制作分层镜像；在 CI 中开启缓存。

---

## 14) 附：一键验证命令

**列出模型**（backend 容器内执行）：

```bash
curl -s -H "Authorization: Bearer ${LLM_API_KEY}" \
  http://llama_server:8080/v1/models | jq .
```

**一次性对话**：

```bash
curl -s -H 'Content-Type: application/json' -H "Authorization: Bearer ${LLM_API_KEY}" \
  -d '{
    "model": "'"${HF_FILENAME}"'",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Say hi in one short sentence."}
    ],
    "stream": false
  }' http://llama_server:8080/v1/chat/completions | jq .choices[0].message.content
```

---

**完成！** 以上为一体化、可落地的最终版实施指南；已经将原三份文档的步骤与注意点合并、去重并修正错误（`hf_transfer`、`curl` 健康检查、heredoc 顶格、pgvector 余弦索引等）。如需我为你的仓库产出 PR 版 diff 或按你项目结构生成最小可运行示例，请告知。
