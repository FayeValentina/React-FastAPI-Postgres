# 在本项目引入轻量本地大模型（llama.cpp + GGUF, OpenAI 兼容 API）实施指南

> 目标：在现有微服务架构中，通过“命名卷 + 预下载(init) 容器 + llama.cpp OpenAI 兼容服务器（llama_server）”方式，新增本地 LLM 服务。后端以 OpenAI SDK 调用，不对公网暴露；前端通过 WebSocket 与后端交互，流式显示回复。适配本地开发与生产（OCI ARM）两套 Compose。

---

## 1) 架构与路径总览

- 形态：独立容器 `llama_server`（OpenAI 兼容 HTTP），不嵌入后端进程。
- 数据：命名卷 `models_data` 持久化模型权重（GGUF）。
- 预热：`llm_init` 服务一次性下载模型到卷；`llama_server` 只读挂载，启动即用。
- 调用：后端以 OpenAI SDK 走内网 `http://llama_server:8080/v1`，前端通过 WebSocket 与后端交互。
- 暴露：`llama_server` 仅 `expose` 给内部网络，不做对外端口映射。

调用链：Frontend → WebSocket → Backend（OpenAI SDK）→ llama_server → Backend → Frontend（stream）

---

## 2) 资源与前置条件

- 机器：OCI ARM（VM.Standard.A1.Flex，4 OCPU / 24GB RAM / 120GB+ 磁盘）。
- Docker/Compose：Docker Engine 与 Docker Compose v2（建议 ≥ v2.20）。
- 模型选型：Gemma 3 4B Instruct 的 GGUF 量化，如 `gemma-3-4b-it-q4_0.gguf`（约 3GB）。
- 访问授权：如模型为 gated，需要 Hugging Face 账号并同意许可，准备 `HF_TOKEN`。
- 后端依赖：`openai>=1.40.0`（Python SDK v1），FastAPI 已有。

---

## 3) 环境变量与约定

在 `.env.dev` / `.env.prod` 中新增（请勿提交敏感 Token 到仓库）：

```
# llama_server Base URL 与 API Key（仅内部用）
LLM_BASE_URL=http://llama_server:8080/v1
LLM_API_KEY=sk-local

# 模型下载参数（按需调整）
HF_TOKEN=xxx_your_hf_token_xxx
HF_REPO_ID=google/gemma-3-4b-it-gguf  # 请以实际 Hugging Face 仓库 ID 为准
HF_FILENAME=gemma-3-4b-it-q4_0.gguf
HF_REVISION=main

# llama_server 使用的模型名（默认读取 HF_FILENAME）
LLM_MODEL=${HF_FILENAME}
```

说明：
- `LLM_API_KEY` 会作为 llama.cpp server 的 `--api-key`，用于内部鉴权；后端请求需带 `Authorization: Bearer sk-local`。
- `HF_*` 用于 `llm_init` 拉取权重；如更换模型，仅需修改并重新运行 `llm_init`。
- `LLM_MODEL` 默认读取 `HF_FILENAME`，避免变量不同步。
- 请在 Hugging Face 网站核实 `HF_REPO_ID` 与 `HF_FILENAME` 是否匹配，否则模型将无法下载。

---

## 4) docker-compose 变更（dev / prod 同步）

在 `docker-compose.dev.yml` 与 `docker-compose.prod.yml` 中，新增命名卷与两个服务（注意与现有内容合并，避免覆盖）。

示例片段：

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
      # 可选降噪：- --log-disable
    expose:
      - "8080"
    volumes:
      - models_data:/models:ro
    restart: unless-stopped

  # 3) 让 backend 能够调用本地 LLM
  backend:
    # ... 你现有的镜像/构建配置 ...
    environment:
      # 保留现有变量并新增：
      - LLM_BASE_URL=${LLM_BASE_URL}
      - LLM_API_KEY=${LLM_API_KEY}
    depends_on:
      llama_server:
        condition: service_healthy
    # 其余保持不变
```

要点：
- 不对外暴露 `llama_server` 端口，仅通过服务名在 Compose 网络中访问。
- `backend` 通过 `depends_on` 确保在 `llama_server` 可用后再启动（首次启动仍可能需等待模型加载）。
- `llm_init` 与 `llama_server` 需加入现有的 `dbNetWork` 网络，以便 `backend` 能解析其服务名。
- 首次部署前可先运行 `docker compose run --rm llm_init` 进行预下载，避免 `up` 时等待过长；首次推理时模型加载亦会有额外延迟属正常现象。

---

## 5) 启动与验证（本地 / 生产一致）

- 第一次仅下载：
  - `docker compose -f docker-compose.dev.yml run --rm llm_init`
- 启动服务：
  - dev：`docker compose -f docker-compose.dev.yml up --build`
  - prod：`docker compose -f docker-compose.prod.yml up --build -d`
- 验证 LLM API（从 backend 容器内访问，确保走内网）：
  - `docker compose exec backend sh -lc "curl -s -H 'Authorization: Bearer ${LLM_API_KEY}' http://llama_server:8080/v1/models"`
  - 简单对话（返回需数秒）：

```bash
docker compose exec backend sh -lc "curl -s -H 'Content-Type: application/json' -H 'Authorization: Bearer ${LLM_API_KEY}' \
  -d '{
    "model": "'"${HF_FILENAME}"'",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Say hi in one short sentence."}
    ],
    "stream": false
  }' http://llama_server:8080/v1/chat/completions | jq .choices[0].message.content"
```

---

## 6) 后端改造方案（WebSocket + OpenAI SDK）

建议新增一个专用模块（示例）：
- `backend/app/modules/llm/`：封装客户端与业务逻辑
- `backend/app/api/v1/endpoints/llm_ws.py`：WebSocket 端点
- 在 Pydantic 配置中加入 `LLM_BASE_URL`、`LLM_API_KEY`
- Poetry 依赖：`openai>=1.40.0`

示例代码要点（精简版）：

1) 配置（示意）：
```python
# app/core/settings.py（或项目中现有 Settings 定义处）
import os
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    LLM_BASE_URL: str = "http://llama_server:8080/v1"
    LLM_API_KEY: str = "sk-local"
    # 默认从 HF_FILENAME 读取，减少变量不同步
    LLM_MODEL: str = Field(default_factory=lambda: os.getenv("HF_FILENAME", "gemma-3-4b-it-q4_0.gguf"))

settings = Settings()
```

2) LLM 客户端封装：
```python
# app/modules/llm/client.py
from openai import OpenAI
from app.core.settings import settings

client = OpenAI(base_url=settings.LLM_BASE_URL, api_key=settings.LLM_API_KEY)
```

3) WebSocket 路由（流式发送 token）：
```python
# app/api/v1/endpoints/llm_ws.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.modules.llm.client import client

router = APIRouter(prefix="/ws", tags=["llm"])

@router.websocket("/chat")
async def ws_chat(ws: WebSocket):
    await ws.accept()
    history = []
    try:
        while True:
            incoming = await ws.receive_json()
            if incoming.get("type") == "reset":
                history.clear()
                await ws.send_json({"type": "reset_ok"})
                continue

            user_text = (incoming.get("content") or "").strip()
            if not user_text:
                await ws.send_json({"type": "error", "message": "empty content"})
                continue

            history.append({"role": "user", "content": user_text})

            stream = client.chat.completions.create(
                model=settings.LLM_MODEL,  # 建议与 GGUF 文件名一致，或启动时动态获取
                messages=[{"role": "system", "content": "You are a helpful assistant."}] + history,
                stream=True,
                temperature=0.2,
            )

            acc = []
            for chunk in stream:
                delta = chunk.choices[0].delta
                token = getattr(delta, "content", None) or delta.get("content") if isinstance(delta, dict) else None
                if token:
                    acc.append(token)
                    await ws.send_json({"type": "delta", "content": token})

            text = "".join(acc)
            history.append({"role": "assistant", "content": text})
            await ws.send_json({"type": "done"})

    except WebSocketDisconnect:
        pass
```

4) 路由纳入主应用：
```python
# app/api/v1/endpoints/__init__.py 或 main 中 include_router
from app.api.v1.routes import llm_ws
api_router.include_router(llm_ws.router)
```

---

## 7) 前端改造方案（新增 Chat 页面，WebSocket 直连后端）

- 依赖：当前前端已用 Vite + React + TS，确保 `.env.*` 已配置 `VITE_API_URL` 指向后端（HTTP）。
- WebSocket URL 通常为：`ws(s)://<backend_domain>/api/v1/ws/chat`（具体前缀以后端路由为准）。如部署在子路径或使用自定义端口，请确认 `VITE_API_URL` 拼装出的地址是否正确。

示例组件（简化）：`frontend/src/pages/Chat.tsx`
```tsx
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
    ws.onclose = () => { /* 可做重连 */ }
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

将该页面加入你的路由（例如在 `src/routes.tsx` 或 `src/App.tsx` 中挂载），并在导航中提供入口。

---

## 8) Nginx 配置建议

- llama_server 不对外暴露，无需在 Nginx 新增反代（保持仅内部访问）。
- 若新增了后端 WebSocket 端点，需确保 Nginx 已正确代理 WebSocket（通常已有；否则参考）：

```nginx
# 例：/api/ 统一转发至 backend（含 WS）
location /api/ {
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 600s;
    proxy_send_timeout 600s;
    proxy_pass http://backend:8000;  # upstream 名称按你现有配置
}
```

如生产开启 HTTPS，请使用 `wss://`；前端拼装 WS URL 时将 `http` 替换为 `ws` 已覆盖该情况。

---

## 9) 运行与调优建议（A1 机器）

- 参数建议：`--ctx-size 8192`（上下文）与 `--parallel 2`（并发）；从保守值开始，根据内存与时延观测调整。
- 观测日志：llama_server 启动时会打印 GGUF 元信息、KV-Cache 分配、吞吐统计等，属正常。
- 性能期望：4B + q4_0 在 A1 上可用，延迟秒级；对流式交互更友好。
- 替代方案：未来可评估 Ollama 或引入更大模型，但会占用更多资源。

---

## 10) 常见问题排查

- 403/401：检查 `HF_TOKEN` 是否有权限；`llm_init` 是否带上 `Authorization` 头；后端请求是否带了 `Bearer ${LLM_API_KEY}`。
- 首次启动很慢：预先运行 `llm_init`；镜像/网络下载受限时等待更久。
- OOM/性能差：使用更低比特量化（如 q4_0 → q3_k_m）、降低 `--ctx-size`、减少并发；必要时换更轻模型。
- WebSocket 不通：Nginx 未透传 `Upgrade`/`Connection` 头或超时设置过短。
- llama_server 不健康：容器日志是否报“找不到模型文件”；确认 `models_data` 卷内有 `.gguf` 文件且路径正确。

---

## 11) 更换/升级模型

1. 修改 `.env.*` 中的 `HF_REPO_ID` / `HF_FILENAME` / `HF_REVISION`。
2. 运行：`docker compose run --rm llm_init`（重新下载到同一命名卷）。
3. 重启：`docker compose up -d llama_server`（或整体重启）。

---

## 12) 与现有仓库规范的对齐

- FastAPI：将 WS 路由置于 `app/api/v1/endpoints/`，使用 `APIRouter(prefix="/ws", tags=["llm"])`。
- 配置：通过 Pydantic Settings 读取 `LLM_BASE_URL` / `LLM_API_KEY`。
- 前端：新增页面置于 `src/pages/` 或按你现有分层（如 `@components/`）。
- 环境：仅在 `.env.*` 注入变量，不向前端暴露服务内部地址（前端只连后端 WS）。

---

## 13) 最小实施清单（建议照此顺序执行）

1. 确认/准备 HF Token 并同意模型许可。
2. 在 `.env.dev` / `.env.prod` 写入上述 `LLM_*` 与 `HF_*` 变量。
3. 按本文修改 `docker-compose.dev.yml` 与 `docker-compose.prod.yml`（新增 `models_data`、`llm_init`、`llama_server`、后端环境变量）。
4. 先运行 `llm_init` 预下载模型；再 `up` 启动全栈。
5. 在 backend 容器内用 `curl` 验证 `/v1/models`、`/v1/chat/completions`。
6. 后端落地 WS 端点并集成 OpenAI SDK；前端新增 Chat 页面。
7. 验证浏览器端到端流式回复；根据表现做调优与限流。

---

## 14) 后续可选优化

- 下载提速：可在 `llm_init` 中改用 `python:3.11-slim` + `huggingface_hub[hf_xet]` 以加速。
- 观测/限流：后端为 LLM 请求添加超时、QPS 限制与审计日志；必要时在 Nginx 层进一步限流。
- 固定快照：通过 `HF_REVISION` 固定到具体 commit，避免上游更新导致重新下载。

---

如需我直接在 compose 与后端/前端中帮你落地上述改动，请告知，我可以继续提交补丁并提供最小可运行示例。
