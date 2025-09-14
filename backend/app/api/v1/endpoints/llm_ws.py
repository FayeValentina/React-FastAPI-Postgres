from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infrastructure.database.postgres_base import get_async_session
from app.modules.llm.client import client
from app.modules.knowledge_base.service import search_similar_chunks
from app.api.dependencies import get_current_user_from_ws
from app.modules.auth.models import User


router = APIRouter(prefix="/ws", tags=["llm"])


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
            if not user_text:
                await ws.send_json({"type": "error", "message": "empty content"})
                continue

            # RAG: 检索相似上下文
            try:
                similar = await search_similar_chunks(db, user_text, settings.RAG_TOP_K)
            except Exception:
                similar = []
            context = "\n---\n".join(getattr(c, "content", str(c)) for c in similar)
            system_prompt = "You are a helpful assistant."
            if context:
                user_text = f"请参考以下资料回答问题，若资料不足请说明：\n{context}\n问题：{user_text}"

            history.append({"role": "user", "content": user_text})

            stream = client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[{"role": "system", "content": system_prompt}] + history,
                stream=True,
                temperature=0.2,
            )

            acc: list[str] = []
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
