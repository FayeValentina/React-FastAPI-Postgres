from __future__ import annotations

import asyncio
import inspect
import json
import logging
from datetime import datetime, timezone
from typing import Annotated, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user
from app.infrastructure.database.postgres_base import get_async_session
from app.infrastructure.redis.redis_pool import redis_connection_manager
from app.modules.auth.models import User
from app.modules.llm import repository as conversation_repository
from app.modules.llm.schemas import (
    ConversationCreate,
    ConversationListItem,
    ConversationListResponse,
    ConversationMessageCreate,
    ConversationResponse,
    MessageAcceptedResponse,
    MessageListResponse,
    MessageResponse,
)
from app.modules.tasks.workers.chat_tasks import process_chat_message
from sse_starlette.sse import EventSourceResponse

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    payload: ConversationCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
) -> ConversationResponse:
    conversation = await conversation_repository.create_conversation(
        db,
        user_id=current_user.id,
        payload=payload,
    )
    return ConversationResponse.from_orm(conversation)


@router.get(
    "/conversations",
    response_model=ConversationListResponse,
)
async def list_conversations(
    limit: Optional[int] = Query(20, ge=1, le=100),
    offset: Optional[int] = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
) -> ConversationListResponse:
    records, total = await conversation_repository.list_conversations(
        db,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )

    items: list[ConversationListItem] = []
    for conversation, preview in records:
        item = ConversationListItem.from_orm(conversation)
        item.last_message_preview = preview
        items.append(item)

    return ConversationListResponse(items=items, total=total)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessageListResponse,
)
async def get_conversation_messages(
    conversation_id: UUID,
    limit: Optional[int] = Query(50, ge=1, le=100),
    before_message_index: Optional[int] = Query(None, ge=0),
    before_created_at: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
) -> MessageListResponse:
    conversation = await conversation_repository.get_conversation_for_user(
        db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    page_size = max(1, min(limit or 50, 100))
    messages = await conversation_repository.list_messages(
        db,
        conversation_id=conversation_id,
        limit=page_size,
        before_message_index=before_message_index,
        before_created_at=before_created_at,
    )

    message_payload = [MessageResponse.from_orm(msg) for msg in messages]

    has_more = len(messages) == page_size
    next_before_index = messages[0].message_index if messages and has_more else None
    next_before_created_at = messages[0].created_at if messages and has_more else None

    return MessageListResponse(
        messages=message_payload,
        next_before_index=next_before_index,
        next_before_created_at=next_before_created_at,
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def send_conversation_message(
    conversation_id: UUID,
    message: ConversationMessageCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
) -> MessageAcceptedResponse:
    conversation = await conversation_repository.get_conversation_for_user(
        db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    content = message.content.strip()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message content cannot be empty")

    request_id = uuid4()
    queued_at = datetime.now(timezone.utc)

    task_payload = {
        "conversation_id": str(conversation_id),
        "user_id": current_user.id,
        "request_id": str(request_id),
        "content": content,
    }

    if message.model:
        task_payload["model"] = message.model
    if message.temperature is not None:
        task_payload["temperature"] = message.temperature
    if message.system_prompt_override is not None:
        task_payload["system_prompt_override"] = message.system_prompt_override
    if message.top_k is not None:
        task_payload["top_k"] = message.top_k

    await process_chat_message.kiq(**task_payload)

    stream_url = f"/api/v1/chat/conversations/{conversation_id}/events"

    return MessageAcceptedResponse(
        conversation_id=conversation_id,
        request_id=request_id,
        queued_at=queued_at,
        stream_url=stream_url,
    )


@router.get(
    "/conversations/{conversation_id}/events",
    response_class=EventSourceResponse,
)
async def stream_conversation_events(
    conversation_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
) -> EventSourceResponse:
    conversation = await conversation_repository.get_conversation_for_user(
        db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    try:
        redis_client = await redis_connection_manager.get_client()
    except Exception as exc:
        logger.exception(
            "Failed to acquire Redis client for SSE",
            extra={"conversation_id": str(conversation_id)},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Event stream unavailable",
        ) from exc

    channel_name = f"chat:{conversation_id}"

    async def event_generator():
        pubsub = redis_client.pubsub()
        try:
            await pubsub.subscribe(channel_name)
            logger.info(
                "Subscribed to chat channel",
                extra={"conversation_id": str(conversation_id)},
            )

            while True:
                if await request.is_disconnected():
                    logger.info(
                        "Client disconnected from SSE",
                        extra={"conversation_id": str(conversation_id)},
                    )
                    break

                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=5.0,
                )
                if message is None:
                    await asyncio.sleep(0.25)
                    continue

                data = message.get("data")
                if data is None:
                    continue

                if isinstance(data, bytes):
                    try:
                        data = data.decode("utf-8")
                    except UnicodeDecodeError:
                        logger.warning(
                            "Failed to decode Redis payload; skipping",
                            extra={"conversation_id": str(conversation_id)},
                        )
                        continue

                yield data

        except asyncio.CancelledError:
            logger.info(
                "SSE task cancelled",
                extra={"conversation_id": str(conversation_id)},
            )
            raise
        except Exception:
            logger.exception(
                "Error in SSE stream",
                extra={"conversation_id": str(conversation_id)},
            )
            error_payload = json.dumps(
                {
                    "type": "error",
                    "conversation_id": str(conversation_id),
                    "message": "stream_failed",
                }
            )
            yield error_payload
            return
        finally:
            try:
                await pubsub.unsubscribe(channel_name)
            except Exception:
                pass

            close_method = getattr(pubsub, "close", None)
            if close_method:
                try:
                    maybe_coro = close_method()
                    if inspect.isawaitable(maybe_coro):
                        await maybe_coro
                except Exception:
                    pass

            logger.info(
                "Unsubscribed from chat channel",
                extra={"conversation_id": str(conversation_id)},
            )

    return EventSourceResponse(event_generator(), ping=15.0)
