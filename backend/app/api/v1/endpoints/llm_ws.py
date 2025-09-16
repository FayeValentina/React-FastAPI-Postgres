from typing import Any, Dict, List

import tiktoken
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


DEFAULT_HISTORY_MAX_TOKENS = 2000
HISTORY_MAX_TOKENS = getattr(settings, "LLM_MAX_HISTORY_TOKENS", DEFAULT_HISTORY_MAX_TOKENS)


def _encoding_for_model(model: str) -> "tiktoken.Encoding":
    try:
        return tiktoken.encoding_for_model(model)
    except Exception:
        return tiktoken.get_encoding("cl100k_base")


def _message_token_length(message: Dict[str, Any], encoding: "tiktoken.Encoding") -> int:
    content = message.get("content", "")
    if not isinstance(content, str):
        content = str(content)
    # 估算消息 token（简单地按内容编码长度 + 常数项）
    return len(encoding.encode(content)) + 4


def trim_history(
    history: List[Dict[str, Any]],
    max_tokens: int = HISTORY_MAX_TOKENS,
    model: str | None = None,
) -> None:
    """限制历史消息的 token 数，超出上限时丢弃最早的对话对。"""

    if not history or max_tokens <= 0:
        return

    encoding = _encoding_for_model(model or settings.LLM_MODEL)
    tokens_per_message = [_message_token_length(msg, encoding) for msg in history]
    total_tokens = sum(tokens_per_message)

    while history and total_tokens > max_tokens:
        removed_tokens = tokens_per_message.pop(0)
        removed = history.pop(0)
        total_tokens -= removed_tokens
        if removed.get("role") == "user" and history and history[0].get("role") == "assistant":
            total_tokens -= tokens_per_message.pop(0)
            history.pop(0)


router = APIRouter(prefix="/ws", tags=["llm"])


@router.websocket("/chat")
async def ws_chat(
    ws: WebSocket,
    current_user: User = Depends(get_current_user_from_ws),
    db: AsyncSession = Depends(get_async_session),
):
    await ws.accept()
    history: List[Dict[str, Any]] = []
    try:
        while True:
            incoming = await ws.receive_json()
            if incoming.get("type") == "reset":
                history.clear()
                await ws.send_json({"type": "reset_ok"})
                continue

            raw_user_text = (incoming.get("content") or "").strip()
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
            if not raw_user_text:
                await ws.send_json({"type": "error", "message": "empty content"})
                continue

            # RAG: 检索相似上下文
            try:
                similar = await search_similar_chunks(db, raw_user_text, settings.RAG_TOP_K)
            except Exception:
                similar = []

            # 限制历史消息长度，避免上下文无限增长
            trim_history(history, HISTORY_MAX_TOKENS, settings.LLM_MODEL)

            # 使用服务层根据语言构建 system_prompt 以及包裹后的 user_text
            system_prompt, final_user_text = await run_in_threadpool(
                prepare_system_and_user, raw_user_text, similar
            )

            # 构造发送给 LLM 的消息：系统提示 + 截断后的历史 + 当前带上下文的问题
            messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
            messages.extend(history)
            messages.append({"role": "user", "content": final_user_text})

            acc: List[str] = []
            async with client.chat.completions.stream(
                model=settings.LLM_MODEL,
                messages=messages,
                temperature=temperature,
            ) as stream:
                async for chunk in stream:
                    if not getattr(chunk, "choices", None):
                        continue
                    delta = chunk.choices[0].delta
                    token = None
                    if hasattr(delta, "content"):
                        token = delta.content
                    elif isinstance(delta, dict):
                        token = delta.get("content")
                    if token:
                        acc.append(token)
                        await ws.send_json({"type": "delta", "content": token})

            text = "".join(acc)
            history.append({"role": "user", "content": raw_user_text})
            history.append({"role": "assistant", "content": text})
            trim_history(history, HISTORY_MAX_TOKENS, settings.LLM_MODEL)
            await ws.send_json({"type": "done"})

    except WebSocketDisconnect:
        pass
