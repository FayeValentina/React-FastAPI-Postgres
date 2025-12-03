"""
聊天对话相关的 Taskiq 任务

负责执行业务流程：
1. 加载会话与历史消息
2. 执行 RAG 检索并推送引用
3. 调用 LLM 生成回答并流式推送 token
4. 在单个事务内持久化用户与助手消息
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from app.broker import broker
from app.core.config import settings
from app.infrastructure.database.postgres_base import AsyncSessionLocal
from app.infrastructure.dynamic_settings import get_dynamic_settings_service
from app.infrastructure.redis.redis_pool import redis_connection_manager
from app.modules.llm.client import client
from app.modules.llm.repository import (
    append_messages,
    get_conversation_for_user,
    get_recent_messages,
    get_message_by_request_id,
    update_conversation_metadata as persist_conversation_metadata,
)
from app.modules.llm.service import prepare_system_and_user
from app.modules.llm.intent_classifier import RouterDecision
from app.modules.llm.conversation_metadata import generate_conversation_metadata
from app.modules.knowledge_base.retrieval import hybrid_search
from app.modules.llm.strategy import StrategyContext, resolve_rag_parameters

logger = logging.getLogger(__name__)

CHAT_QUEUE = "chat"
MAX_HISTORY_MESSAGES = 30
ASSISTANT_FALLBACK_MESSAGE = "抱歉，我暂时无法生成回答，请稍后再试。"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compress_snippet(text: str, limit: int = 500) -> str:
    snippet = (text or "").strip()
    if len(snippet) <= limit:
        return snippet
    return snippet[:limit].rstrip() + "…"


def _build_citations(similar: list[Any]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for idx, item in enumerate(similar or [], start=1):
        chunk = item.chunk
        doc = getattr(chunk, "document", None)
        content = (chunk.content or "")
        citations.append(
            {
                "key": f"CITE{idx}",
                "chunk_id": getattr(chunk, "id", None),
                "document_id": getattr(chunk, "document_id", None),
                "chunk_index": getattr(chunk, "chunk_index", None),
                "title": getattr(doc, "title", None),
                "source_ref": getattr(doc, "source_ref", None),
                "similarity": round(float(getattr(item, "similarity", 0.0)), 4),
                "score": round(float(getattr(item, "score", 0.0)), 4),
                "bm25_score": (
                    round(float(item.bm25_score), 4)
                    if getattr(item, "bm25_score", None) is not None
                    else None
                ),
                "retrieval_source": getattr(item, "retrieval_source", None),
                "content": _compress_snippet(content),
            }
        )
    return citations


def _merge_system_prompts(*candidates: Optional[str]) -> Optional[str]:
    parts = [part.strip() for part in candidates if part]
    if not parts:
        return None
    return "\n\n".join(parts)


def _usage_payload(usage: Any | None) -> Optional[dict[str, int]]:
    if usage is None:
        return None
    payload = {
        "prompt": getattr(usage, "prompt_tokens", None),
        "completion": getattr(usage, "completion_tokens", None),
        "total": getattr(usage, "total_tokens", None),
    }
    if not any(value is not None for value in payload.values()):
        return None
    return payload


def ensure_int(value: Any, fallback: Optional[int] = None) -> Optional[int]:
    if value is None:
        return fallback
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


async def _publish_event(
    redis_client,
    channel: str,
    event_type: str,
    *,
    conversation_id: UUID,
    request_id: UUID,
    **payload: Any,
) -> None:
    base_event = {
        "type": event_type,
        "conversation_id": str(conversation_id),
        "request_id": str(request_id),
        "timestamp": _now_iso(),
    }
    for key, value in payload.items():
        if value is not None:
            base_event[key] = value

    try:
        message = json.dumps(base_event, ensure_ascii=False)
        await redis_client.publish(channel, message)
    except Exception:
        logger.exception(
            "Failed to publish SSE event",
            extra={"conversation_id": str(conversation_id), "event_type": event_type},
        )


@broker.task(
    task_name="refresh_conversation_metadata",
    queue=CHAT_QUEUE,
    retry_on_error=True,
)
async def refresh_conversation_metadata(
    conversation_id: str,
    classifier: dict[str, Any] | None,
) -> None:
    try:
        conversation_uuid = UUID(conversation_id)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid conversation_id for metadata refresh",
            extra={"conversation_id": conversation_id},
        )
        return

    if not isinstance(classifier, dict):
        logger.debug(
            "Skipping metadata refresh due to missing classifier payload",
            extra={"conversation_id": str(conversation_uuid)},
        )
        return

    try:
        classifier_result = RouterDecision.from_payload(classifier)
    except Exception:
        logger.exception(
            "Failed to deserialize classifier payload",
            extra={"conversation_id": str(conversation_uuid)},
        )
        return

    async with AsyncSessionLocal() as db:
        try:
            metadata = await generate_conversation_metadata(
                db,
                conversation_id=conversation_uuid,
                classifier_result=classifier_result,
            )
            if metadata is None:
                await db.rollback()
                logger.debug(
                    "Metadata generation skipped (empty result)",
                    extra={"conversation_id": str(conversation_uuid)},
                )
                return

            updated = await persist_conversation_metadata(
                db,
                conversation_id=conversation_uuid,
                title=metadata.title,
                summary=metadata.summary,
                system_prompt=metadata.system_prompt,
            )
            if not updated:
                await db.rollback()
                logger.warning(
                    "Conversation metadata update skipped (conversation missing)",
                    extra={"conversation_id": str(conversation_uuid)},
                )
                return

            await db.commit()
            logger.info(
                "Conversation metadata refreshed",
                extra={
                    "conversation_id": str(conversation_uuid),
                    "title": metadata.title,
                },
            )
        except Exception:
            await db.rollback()
            logger.exception(
                "Failed to refresh conversation metadata",
                extra={"conversation_id": str(conversation_uuid)},
            )
            raise


@broker.task(
    task_name="process_chat_message",
    queue=CHAT_QUEUE,
    retry_on_error=True,
)
async def process_chat_message(
    conversation_id: str,
    user_id: int,
    request_id: str,
    content: str,
    *,
    model: Optional[str] = None,
    temperature: Optional[float] = 0.7,
    system_prompt_override: Optional[str] = None,
    top_k: Optional[int] = settings.RAG_TOP_K,
) -> None:
    request_uuid = UUID(request_id)
    conversation_uuid = UUID(conversation_id)

    try:
        redis_client = await redis_connection_manager.get_client()
    except Exception:
        logger.exception(
            "Unable to obtain Redis client for chat SSE",
            extra={"conversation_id": conversation_id, "request_id": request_id},
        )
        return

    channel_name = f"chat:{conversation_uuid}"

    async with AsyncSessionLocal() as db:
        conversation = await get_conversation_for_user(
            db,
            conversation_id=conversation_uuid,
            user_id=user_id,
        )

        if conversation is None:
            await _publish_event(
                redis_client,
                channel_name,
                "error",
                conversation_id=conversation_uuid,
                request_id=request_uuid,
                message="conversation_not_found",
            )
            logger.warning(
                "Conversation not found during task processing",
                extra={
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "request_id": request_id,
                },
            )
            return

        # Idempotency check: if assistant message for this request_id already exists,
        # replay it to SSE and exit early to avoid duplicate generations.
        try:
            existing_assistant = await get_message_by_request_id(
                db,
                conversation_id=conversation_uuid,
                request_id=request_uuid,
                role="assistant",
            )
        except Exception:
            existing_assistant = None

        if existing_assistant is not None:
            # Optionally signal recovery, then replay the final content and done.
            await _publish_event(
                redis_client,
                channel_name,
                "progress",
                conversation_id=conversation_uuid,
                request_id=request_uuid,
                stage="recovered",
            )

            # Replay content as a single delta chunk for simplicity.
            if existing_assistant.content:
                await _publish_event(
                    redis_client,
                    channel_name,
                    "delta",
                    conversation_id=conversation_uuid,
                    request_id=request_uuid,
                    content=existing_assistant.content,
                )

            await _publish_event(
                redis_client,
                channel_name,
                "done",
                conversation_id=conversation_uuid,
                request_id=request_uuid,
            )
            return

        dynamic_settings_service = get_dynamic_settings_service()
        try:
            base_config = await dynamic_settings_service.get_all()
        except Exception:
            base_config = settings.dynamic_settings_defaults()

        requested_top_k = top_k
        strategy_ctx = StrategyContext(
            top_k_request=requested_top_k,
            channel="task",
            user_role=None,
        )

        try:
            strategy = await resolve_rag_parameters(
                content,
                base_config,
                request_ctx=strategy_ctx,
            )
            strategy_config = strategy.config
        except Exception:
            logger.exception(
                "Failed to resolve RAG strategy",
                extra={"conversation_id": conversation_id, "request_id": request_id},
            )
            strategy = None
            strategy_config = {"RAG_TOP_K": settings.RAG_TOP_K}

        decision = strategy.router_decision if strategy else None

        await _publish_event(
            redis_client,
            channel_name,
            "progress",
            conversation_id=conversation_uuid,
            request_id=request_uuid,
            stage="router",
            mode=decision.mode if decision else None,
        )

        if decision and decision.mode == "chat":
            assistant_message = decision.reply or ASSISTANT_FALLBACK_MESSAGE

            await _publish_event(
                redis_client,
                channel_name,
                "citations",
                conversation_id=conversation_uuid,
                request_id=request_uuid,
                citations=[],
            )
            if assistant_message:
                await _publish_event(
                    redis_client,
                    channel_name,
                    "delta",
                    conversation_id=conversation_uuid,
                    request_id=request_uuid,
                    content=assistant_message,
                )
            try:
                await append_messages(
                    db,
                    conversation_id=conversation_uuid,
                    request_id=request_uuid,
                    entries=[
                        ("user", content),
                        ("assistant", assistant_message),
                    ],
                )
                await db.commit()

                if strategy and getattr(strategy, "router_decision", None):
                    classifier_payload = strategy.router_decision.to_payload()
                    await refresh_conversation_metadata.kiq(
                        conversation_id=str(conversation_uuid),
                        classifier=classifier_payload,
                    )
            except Exception:
                await db.rollback()
                await _publish_event(
                    redis_client,
                    channel_name,
                    "error",
                    conversation_id=conversation_uuid,
                    request_id=request_uuid,
                    message="persist_failed",
                )
                logger.exception(
                    "Failed to persist chat transcript",
                    extra={"conversation_id": conversation_id, "request_id": request_id},
                )
                return

            await _publish_event(
                redis_client,
                channel_name,
                "done",
                conversation_id=conversation_uuid,
                request_id=request_uuid,
                token_usage=None,
            )
            return

        raw_top_k = strategy_config.get("RAG_TOP_K")
        strategy_top_k = ensure_int(raw_top_k, fallback=settings.RAG_TOP_K)
        top_k_value = strategy_top_k if strategy_top_k and strategy_top_k > 0 else settings.RAG_TOP_K

        await _publish_event(
            redis_client,
            channel_name,
            "progress",
            conversation_id=conversation_uuid,
            request_id=request_uuid,
            stage="retrieval",
        )

        effective_query = strategy.processed_query if strategy and strategy.processed_query else content

        try:
            similar = await hybrid_search(
                db,
                effective_query,
                top_k_value,
                config=strategy_config,
            )
        except Exception:
            logger.exception(
                "RAG retrieval failed",
                extra={"conversation_id": conversation_id, "request_id": request_id},
            )
            similar = []

        citations_payload = _build_citations(similar)
        await _publish_event(
            redis_client,
            channel_name,
            "citations",
            conversation_id=conversation_uuid,
            request_id=request_uuid,
            citations=citations_payload,
        )

        history_records = await get_recent_messages(
            db,
            conversation_id=conversation_uuid,
            limit=MAX_HISTORY_MESSAGES,
        )
        history_payload = [{"role": msg.role, "content": msg.content} for msg in history_records]

        base_system_prompt, wrapped_user_text = await prepare_system_and_user(
            content,
            similar,
        )

        merged_system_prompt = _merge_system_prompts(
            system_prompt_override,
            conversation.system_prompt,
            base_system_prompt,
        ) or base_system_prompt

        configured_model = (settings.CHAT_MODEL or "").strip()
        selected_model = configured_model or (conversation.model or "").strip() or "gpt-4-turbo"

        fallback_temperature = (
            conversation.temperature if conversation.temperature is not None else 0.7
        )
        effective_temperature = temperature if temperature is not None else fallback_temperature

        llm_messages = [{"role": "system", "content": merged_system_prompt}] + history_payload + [
            {"role": "user", "content": wrapped_user_text}
        ]

        await _publish_event(
            redis_client,
            channel_name,
            "progress",
            conversation_id=conversation_uuid,
            request_id=request_uuid,
            stage="generating",
        )

        assistant_tokens: list[str] = []
        final_usage: dict[str, int] | None = None

        try:
            stream = await client.chat.completions.create(
                model=selected_model,
                messages=llm_messages,
                temperature=effective_temperature,
                stream=True,
            )

            async for chunk in stream:
                if not getattr(chunk, "choices", None):
                    continue
                choice = chunk.choices[0]
                delta = getattr(choice, "delta", None)
                if delta and getattr(delta, "content", None):
                    token = delta.content
                    assistant_tokens.append(token)
                    await _publish_event(
                        redis_client,
                        channel_name,
                        "delta",
                        conversation_id=conversation_uuid,
                        request_id=request_uuid,
                        content=token,
                    )

                usage_payload = _usage_payload(getattr(chunk, "usage", None))
                if usage_payload:
                    final_usage = usage_payload

        except asyncio.CancelledError:
            logger.info(
                "LLM streaming cancelled",
                extra={"conversation_id": conversation_id, "request_id": request_id},
            )
            raise
        except Exception as exc:
            await _publish_event(
                redis_client,
                channel_name,
                "error",
                conversation_id=conversation_uuid,
                request_id=request_uuid,
                message="llm_stream_failed",
                detail=str(exc),
            )
            logger.exception(
                "LLM streaming failed",
                extra={"conversation_id": conversation_id, "request_id": request_id},
            )
            return

        assistant_message = "".join(assistant_tokens)
        if not assistant_message.strip():
            assistant_message = ASSISTANT_FALLBACK_MESSAGE

        try:
            await append_messages(
                db,
                conversation_id=conversation_uuid,
                request_id=request_uuid,
                entries=[
                    ("user", content),
                    ("assistant", assistant_message),
                ],
            )
            await db.commit()

            if strategy and getattr(strategy, "router_decision", None):
                classifier_payload = strategy.router_decision.to_payload()
                await refresh_conversation_metadata.kiq(
                    conversation_id=str(conversation_uuid),
                    classifier=classifier_payload,
                )
        except Exception:
            await db.rollback()
            await _publish_event(
                redis_client,
                channel_name,
                "error",
                conversation_id=conversation_uuid,
                request_id=request_uuid,
                message="persist_failed",
            )
            logger.exception(
                "Failed to persist chat transcript",
                extra={"conversation_id": conversation_id, "request_id": request_id},
            )
            return

        await _publish_event(
            redis_client,
            channel_name,
            "done",
            conversation_id=conversation_uuid,
            request_id=request_uuid,
            token_usage=final_usage,
        )
