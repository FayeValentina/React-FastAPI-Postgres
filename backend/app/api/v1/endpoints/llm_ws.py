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


MAX_HISTORY_MESSAGES = 15


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
            if incoming.get("type") == "reset":
                history.clear()
                await ws.send_json({"type": "reset_ok"})
                continue

            user_text = (incoming.get("content") or "").strip()
            # temperature 参数：前端可传入，默认 0.2，范围夹紧到 [0.0, 2.0]
            raw_temp = incoming.get("temperature", None)
            temperature = 0.2
            if raw_temp is not None:
                try:
                    temperature = float(raw_temp)
                except (TypeError, ValueError):
                    temperature = 0.2
            if temperature < 0.0:
                temperature = 0.0
            if temperature > 2.0:
                temperature = 2.0
            if not user_text:
                await ws.send_json({"type": "error", "message": "empty content"})
                continue

            # RAG: 检索相似上下文
            try:
                similar = await search_similar_chunks(db, user_text, settings.RAG_TOP_K)
            except Exception:
                similar = []

            # 使用服务层根据语言构建 system_prompt 以及包裹后的 user_text
            system_prompt, user_text = await run_in_threadpool(prepare_system_and_user, user_text, similar)

            history.append({"role": "user", "content": user_text})
            if len(history) > MAX_HISTORY_MESSAGES:
                del history[:-MAX_HISTORY_MESSAGES]

            acc: list[str] = []
            async with client.chat.completions.stream(
                model=settings.LLM_MODEL,
                messages=[{"role": "system", "content": system_prompt}] + history,
                temperature=temperature,
            ) as stream:
                async for event in stream:
                    # 1. 智能地解包，处理 ChunkEvent 包装器或原始 Chunk 对象
                    chunk = getattr(event, "chunk", event)
                    
                    # 2. 安全且清晰地访问 token 内容
                    # openai v1+ 保证了 chunk.choices 是一个列表
                    if chunk.choices:
                        delta = chunk.choices[0].delta
                        token = delta.content
                        if token:
                            acc.append(token)
                            await ws.send_json({"type": "delta", "content": token})

            text = "".join(acc)
            history.append({"role": "assistant", "content": text})
            if len(history) > MAX_HISTORY_MESSAGES:
                del history[:-MAX_HISTORY_MESSAGES]
            await ws.send_json({"type": "done"})

    except WebSocketDisconnect:
        pass
