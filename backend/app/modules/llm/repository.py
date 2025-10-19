from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Sequence, Tuple
from uuid import UUID

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

from .models import Conversation, Message
from .schemas import ConversationCreate

MAX_PAGE_SIZE = 100


def _normalize_pagination(limit: int | None, offset: int | None) -> tuple[int, int]:
    limit_value = limit or 20
    limit_value = max(1, min(limit_value, MAX_PAGE_SIZE))
    offset_value = max(0, offset or 0)
    return limit_value, offset_value


async def create_conversation(
    db: AsyncSession,
    *,
    user_id: int,
    payload: ConversationCreate,
) -> Conversation:
    title = (payload.title or "New Chat").strip() or "New Chat"
    requested_model = (payload.model or "").strip()
    conversation_model = requested_model or (settings.CHAT_MODEL or "").strip() or "gpt-4-turbo"

    conversation = Conversation(
        user_id=user_id,
        title=title,
        model=conversation_model,
    )

    if payload.temperature is not None:
        conversation.temperature = payload.temperature
    if payload.system_prompt is not None:
        conversation.system_prompt = payload.system_prompt

    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def list_conversations(
    db: AsyncSession,
    *,
    user_id: int,
    limit: int | None = None,
    offset: int | None = None,
) -> tuple[list[tuple[Conversation, Optional[str]]], int]:
    page_size, page_offset = _normalize_pagination(limit, offset)

    last_message_subquery = (
        select(Message.content)
        .where(Message.conversation_id == Conversation.id)
        .order_by(Message.message_index.desc())
        .limit(1)
        .scalar_subquery()
    )

    stmt: Select = (
        select(Conversation, last_message_subquery.label("last_message_preview"))
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .offset(page_offset)
        .limit(page_size)
    )

    rows = await db.execute(stmt)
    items: list[tuple[Conversation, Optional[str]]] = []
    for conversation, preview in rows.all():
        preview_source: Optional[str] = conversation.summary or preview
        formatted_preview: Optional[str] = preview_source
        if formatted_preview and len(formatted_preview) > 200:
            formatted_preview = formatted_preview[:200].rstrip() + "…"
        items.append((conversation, formatted_preview))

    total_stmt = select(func.count()).select_from(Conversation).where(Conversation.user_id == user_id)
    total = await db.scalar(total_stmt)

    return items, int(total or 0)


async def get_conversation_for_user(
    db: AsyncSession,
    *,
    conversation_id: UUID,
    user_id: int,
) -> Optional[Conversation]:
    stmt = (
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .where(Conversation.user_id == user_id)
    )
    return await db.scalar(stmt)


async def list_messages(
    db: AsyncSession,
    *,
    conversation_id: UUID,
    limit: int | None = None,
    before_message_index: Optional[int] = None,
    before_created_at: Optional[datetime] = None,
) -> list[Message]:
    page_size = max(1, min(limit or 50, MAX_PAGE_SIZE))

    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.message_index.desc(), Message.id.desc())
        .limit(page_size)
    )

    if before_message_index is not None:
        stmt = stmt.where(Message.message_index < before_message_index)

    if before_created_at is not None:
        stmt = stmt.where(Message.created_at < before_created_at)

    result = await db.scalars(stmt)
    records = list(result)
    records.reverse()
    return records


async def get_recent_messages(
    db: AsyncSession,
    *,
    conversation_id: UUID,
    limit: int,
) -> list[Message]:
    page_size = max(1, min(limit, MAX_PAGE_SIZE))
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.message_index.desc(), Message.id.desc())
        .limit(page_size)
    )
    result = await db.scalars(stmt)
    records = list(result)
    records.reverse()
    return records


async def get_message_by_request_id(
    db: AsyncSession,
    *,
    conversation_id: UUID,
    request_id: UUID,
    role: Optional[str] = None,
) -> Optional[Message]:
    """Fetch a single message by conversation + request_id, optionally filtered by role.

    Returns the latest matching row by (message_index desc, id desc) if multiple exist.
    """
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .where(Message.request_id == request_id)
        .order_by(Message.message_index.desc(), Message.id.desc())
        .limit(1)
    )
    if role:
        stmt = stmt.where(Message.role == role)

    return await db.scalar(stmt)

async def append_messages(
    db: AsyncSession,
    *,
    conversation_id: UUID,
    request_id: UUID,
    entries: Sequence[Tuple[str, str]],
) -> list[Message]:
    """
    Appends messages within the caller's transaction.
    This function is now safe to be called from a background task wrapped in a transaction.
    """
    if not entries:
        return []

    # This function now expects to be called within an existing transaction.
    # We remove the `async with db.begin():` block.

    # Lock the parent conversation row first so concurrent writers serialize on the same chat
    conversation_lock_stmt = (
        select(Conversation.id)
        .where(Conversation.id == conversation_id)
        .with_for_update()
    )
    conversation_result = await db.execute(conversation_lock_stmt)
    if conversation_result.scalar_one_or_none() is None:
        raise ValueError(f"Conversation {conversation_id} not found when appending messages")

    max_stmt = select(func.max(Message.message_index)).where(Message.conversation_id == conversation_id)
    result = await db.execute(max_stmt)
    last_index = result.scalar_one_or_none() or 0
    next_index = last_index + 1

    persisted: list[Message] = []
    for role, content in entries:
        message = Message(
            conversation_id=conversation_id,
            message_index=next_index,
            role=role,
            content=content,
            request_id=request_id,
        )
        db.add(message)
        persisted.append(message)
        next_index += 1

    # Also update the conversation's updated_at timestamp
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(updated_at=func.now())
    )

    # Flush the session to assign IDs to the new message objects
    # before the transaction is committed by the caller.
    await db.flush()

    return persisted


async def update_conversation_metadata(
    db: AsyncSession,
    *,
    conversation_id: UUID,
    title: str,
    summary: str | None,
    system_prompt: str,
) -> bool:
    values: dict[str, Any] = {
        "title": title,
        "system_prompt": system_prompt,
        "updated_at": func.now(),
    }
    if summary is not None:
        values["summary"] = summary

    result = await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(**values)
        .returning(Conversation.id)
    )

    updated = result.scalar_one_or_none()
    if updated is None:
        return False

    await db.flush()
    return True


async def delete_conversation(
    db: AsyncSession,
    *,
    conversation_id: UUID,
    user_id: int,
) -> bool:
    stmt = (
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .where(Conversation.user_id == user_id)
    )
    conversation = await db.scalar(stmt)
    if conversation is None:
        return False

    await db.delete(conversation)
    await db.commit()
    return True
