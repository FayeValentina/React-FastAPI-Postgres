from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, TYPE_CHECKING

from app.core.config import settings
from app.modules.llm.client import classifier_client

if TYPE_CHECKING:  # pragma: no cover
    from .strategy import StrategyContext

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = (
    "You are a chat router deciding whether a user query should be answered directly or backed by a knowledge search.\n"
    "ALWAYS reply with a single JSON object containing:\n"
    '  - mode: \"chat\" or \"search\"\n'
    "  - reason: short English explanation of your choice\n"
    "  - reply: final assistant message when mode=chat, otherwise null\n"
    "  - search_query: improved retrieval query when mode=search, otherwise null\n"
    "Rules:\n"
    "1. Pick mode=\"chat\" only for greetings, meta-conversation, or purely social content. Provide the final reply there.\n"
    "2. Pick mode=\"search\" for anything that could benefit from knowledge, troubleshooting, or contextual documents. Provide a precise retrieval query.\n"
    "3. The JSON must not include extra keys, markdown, or commentary.\n"
    "4. Replies must stay under 120 words. Search queries should be <= 200 characters.\n"
    'Example: {"mode":"search","reason":"User needs documentation context","reply":null,"search_query":"Steps to configure Redis sentinel in production"}\n'
)


def _sanitize_text(value: Any, *, limit: int | None = None) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if limit is not None and len(text) > limit:
        text = text[:limit].rstrip()
    return text or None


@dataclass(slots=True)
class RouterDecision:
    mode: str
    reason: str | None = None
    reply: str | None = None
    search_query: str | None = None
    raw_response: Dict[str, Any] | None = None
    request_payload: Dict[str, Any] | None = None
    fallback: bool = False
    error: str | None = None

    def to_payload(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "reason": self.reason,
            "reply": self.reply,
            "search_query": self.search_query,
            "raw_response": self.raw_response,
            "request_payload": self.request_payload,
            "fallback": self.fallback,
            "error": self.error,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "RouterDecision":
        return cls(
            mode=str(payload.get("mode") or "search"),
            reason=_sanitize_text(payload.get("reason")),
            reply=_sanitize_text(payload.get("reply")),
            search_query=_sanitize_text(payload.get("search_query")),
            raw_response=payload.get("raw_response") if isinstance(payload.get("raw_response"), dict) else None,
            request_payload=payload.get("request_payload") if isinstance(payload.get("request_payload"), dict) else None,
            fallback=bool(payload.get("fallback", False)),
            error=_sanitize_text(payload.get("error")),
        )


def _build_payload(query: str, ctx: "StrategyContext") -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "query": query,
        "channel": ctx.channel,
        "top_k_request": ctx.top_k_request,
        "document_id": ctx.document_id,
        "user_role": ctx.user_role,
    }
    if ctx.metadata:
        preview: Dict[str, Any] = {}
        for idx, (key, value) in enumerate(ctx.metadata.items()):
            if idx >= 6:
                break
            if isinstance(value, (str, int, float, bool)) or value is None:
                preview[key] = value
            else:
                preview[key] = str(value)
        if preview:
            payload["metadata"] = preview
    return payload


async def route_query(query: str, ctx: "StrategyContext") -> RouterDecision:
    normalized = (query or "").strip()
    if not normalized:
        return RouterDecision(mode="chat", reply="", reason="empty_query", fallback=True)

    payload = _build_payload(normalized, ctx)
    response = None
    last_error: Optional[BaseException] = None

    for attempt in range(2):
        try:
            response = await classifier_client.chat.completions.create(
                model=settings.CLASSIFIER_MODEL,
                messages=[
                    {"role": "system", "content": PROMPT_TEMPLATE},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                temperature=0.0,
                top_p=0.0,
                max_tokens=256,
                response_format={"type": "json_object"},
            )
            last_error = None
            break
        except asyncio.TimeoutError as exc:
            last_error = exc
            logger.warning("router timeout attempt=%s", attempt + 1)
        except Exception as exc:  # pragma: no cover - network/SDK exceptions
            last_error = exc
            logger.warning("router failed attempt=%s: %s", attempt + 1, exc)
        if attempt == 0:
            await asyncio.sleep(0.1)

    if response is None:
        error_label = "timeout" if isinstance(last_error, asyncio.TimeoutError) else "exception"
        return RouterDecision(
            mode="search",
            reason=error_label,
            fallback=True,
            error=str(last_error) if last_error else error_label,
            request_payload=payload,
        )

    choice = response.choices[0] if response.choices else None
    if not choice or not getattr(choice, "message", None):
        return RouterDecision(
            mode="search",
            reason="empty_message",
            fallback=True,
            error="empty_message",
            request_payload=payload,
        )

    raw_content = _unwrap_content(choice.message.content)
    logger.info("router raw response: %s", raw_content[:512])

    try:
        parsed: Dict[str, Any] = json.loads(raw_content)
    except Exception as exc:  # pragma: no cover - guard against invalid json
        logger.warning("router invalid json: %s", exc)
        return RouterDecision(
            mode="search",
            reason="json_error",
            fallback=True,
            error=str(exc),
            raw_response={"raw": raw_content[:512]},
            request_payload=payload,
        )

    mode = str(parsed.get("mode") or "").strip().lower()
    if mode not in {"chat", "search"}:
        mode = "search"

    reason = _sanitize_text(parsed.get("reason"), limit=120)
    reply = _sanitize_text(parsed.get("reply"), limit=600) if mode == "chat" else None
    search_query = _sanitize_text(parsed.get("search_query"), limit=600) if mode == "search" else None

    return RouterDecision(
        mode=mode,
        reason=reason,
        reply=reply,
        search_query=search_query,
        raw_response={"raw": raw_content[:512], "parsed": parsed},
        request_payload=payload,
    )


def _unwrap_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        pieces: list[str] = []
        for part in content:
            if isinstance(part, str):
                pieces.append(part)
            elif isinstance(part, dict):
                text = part.get("text") or part.get("content")
                if isinstance(text, str):
                    pieces.append(text)
        return "".join(pieces)
    return str(content or "")


__all__ = ["RouterDecision", "route_query"]
