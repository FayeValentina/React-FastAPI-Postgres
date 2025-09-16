from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infrastructure.database.postgres_base import get_async_session
from app.modules.llm.client import client
from app.modules.llm.service import prepare_system_and_user
from app.modules.knowledge_base.service import search_similar_chunks
from app.api.dependencies import get_current_user_from_ws
from app.modules.auth.models import User

router = APIRouter(prefix="/ws", tags=["llm"])

# 控制历史长度，避免上下文过大
MAX_HISTORY_MESSAGES = 15

def _clamp_temperature(raw) -> float:
    try:
        t = float(raw)
    except (TypeError, ValueError):
        return 0.2
    return max(0.0, min(2.0, t))

@router.websocket("/chat")
async def ws_chat(
    ws: WebSocket,
    current_user: User = Depends(get_current_user_from_ws),
    db: AsyncSession = Depends(get_async_session),
):
    await ws.accept()
    history: list[dict] = []

    try:
        while True:
            incoming = await ws.receive_json()

            # 客户端请求清空会话
            if incoming.get("type") == "reset":
                history.clear()
                await ws.send_json({"type": "reset_ok"})
                continue

            user_text = (incoming.get("content") or "").strip()
            if not user_text:
                await ws.send_json({"type": "error", "message": "empty content"})
                continue

            temperature = _clamp_temperature(incoming.get("temperature", None))

            # RAG: 检索相似上下文（失败时回退为空）
            try:
                similar = await search_similar_chunks(db, user_text, settings.RAG_TOP_K)
            except Exception:
                similar = []

            # 由服务层生成 system_prompt，并对 user_text 做包装（语言/模板等）
            system_prompt, wrapped_user_text = await run_in_threadpool(
                prepare_system_and_user, user_text, similar
            )

            # 追加到历史（只保留最近 N 条）
            history.append({"role": "user", "content": wrapped_user_text})
            if len(history) > MAX_HISTORY_MESSAGES:
                del history[:-MAX_HISTORY_MESSAGES]

            # —— OpenAI Chat Completions：异步流式 —— 
            # 官方模式：create(..., stream=True) → async for chunk in stream
            # 参考：openai-python README / 社区示例
            # 可选：开启用量统计（视服务端实现而定）
            # stream_options = {"include_usage": True}
            acc: list[str] = []
            try:
                stream = await client.chat.completions.create(
                    model=settings.LLM_MODEL,
                    messages=[{"role": "system", "content": system_prompt}] + history,
                    temperature=temperature,
                    stream=True,
                    # stream_options=stream_options,  # 如需用量统计再开启
                )

                async for chunk in stream:
                    # 防御性判空：choices 可能为空；首块 delta 可能只有 role
                    if not getattr(chunk, "choices", None):
                        continue
                    choice = chunk.choices[0]
                    delta = getattr(choice, "delta", None)
                    if not delta:
                        continue

                    token = getattr(delta, "content", None)
                    if token:
                        acc.append(token)
                        await ws.send_json({"type": "delta", "content": token})

                # 结束：汇总文本，入历史
                text = "".join(acc)
                history.append({"role": "assistant", "content": text})
                if len(history) > MAX_HISTORY_MESSAGES:
                    del history[:-MAX_HISTORY_MESSAGES]

                await ws.send_json({"type": "done"})

            except Exception as e:
                # 将错误回传给前端，便于 UI 做降级提示
                await ws.send_json(
                    {"type": "error", "message": f"stream_failed: {e.__class__.__name__}"}
                )

    except WebSocketDisconnect:
        # 客户端断开，静默结束
        return
