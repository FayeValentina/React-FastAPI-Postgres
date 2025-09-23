from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Tuple, TYPE_CHECKING

from app.core.config import settings
from app.modules.llm.client import classifier_client

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from .strategy import StrategyContext


logger = logging.getLogger(__name__)


PROMPT_TEMPLATE = (
    "You are an intent classification assistant for a RAG retrieval system. "
    "Respond with a compact JSON object describing the query scenario. "
    "Base scenarios are: broad, precise, question, document_focus. "
    "If the query implies a more specific intent, you may return labels such as "
    "troubleshooting, procedural, compare or other concise descriptors. "
    "Always include fields: scenario (string), confidence (float 0-1), reason (string, <= 60 words). "
    "Optionally include tags as an array of strings for secondary hints. "
    "Use scenario=\"unknown\" when uncertain. Never include extra commentary."
)


@dataclass(slots=True)
class ClassificationResult:
    scenario: str | None
    confidence: float | None
    reason: str | None
    tags: Tuple[str, ...] = ()
    raw_response: Dict[str, Any] | None = None
    source: str = "llm"
    fallback: bool = False
    error: str | None = None

    def to_log_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"source": self.source}
        if self.scenario:
            payload["scenario"] = self.scenario
        if self.confidence is not None:
            payload["confidence"] = round(float(self.confidence), 4)
        if self.reason:
            payload["reason"] = self.reason
        if self.tags:
            payload["tags"] = list(self.tags)
        if self.fallback:
            payload["fallback"] = True
        if self.error:
            payload["error"] = self.error
        return payload


def _normalize_tags(raw: Any) -> Tuple[str, ...]:
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, Iterable):
        normalized = []
        for item in raw:
            if isinstance(item, str):
                stripped = item.strip()
                if stripped:
                    normalized.append(stripped)
        return tuple(dict.fromkeys(normalized))
    return ()


def _unwrap_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        pieces: list[str] = []
        for part in content:
            text = None
            if isinstance(part, str):
                text = part
            elif isinstance(part, dict):
                text = part.get("text") or part.get("content")
            else:
                text = getattr(part, "text", None)
                if text is None:
                    text = getattr(part, "content", None)
            if isinstance(text, str):
                pieces.append(text)
        return "".join(pieces)
    return str(content or "")


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


def _should_skip_call(query: str, ctx: "StrategyContext") -> str | None:
    if not query:
        return "empty_query"
    if ctx.document_id is not None:
        return "document_scoped"
    if len(query) < 3:
        return "query_too_short"
    return None


async def classify(query: str, ctx: "StrategyContext") -> ClassificationResult:
    normalized = (query or "").strip()
    skip_reason = _should_skip_call(normalized, ctx)
    if skip_reason:
        return ClassificationResult(
            scenario=None,
            confidence=None,
            reason=f"skip:{skip_reason}",
            raw_response={"skip_reason": skip_reason},
            fallback=True,
        )

    payload = _build_payload(normalized, ctx)
    timeout_seconds = max(0.1, settings.RAG_STRATEGY_LLM_CLASSIFIER_TIMEOUT_MS / 1000.0)

    response = None
    last_error: Optional[BaseException] = None
    max_attempts = 2

    for attempt in range(max_attempts):
        try:
            response = await asyncio.wait_for(
                classifier_client.chat.completions.create(
                    model=settings.RAG_STRATEGY_LLM_CLASSIFIER_MODEL,
                    messages=[
                        {"role": "system", "content": PROMPT_TEMPLATE},
                        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                    ],
                    temperature=0.0,
                    top_p=0.0,
                    max_tokens=256,
                    response_format={"type": "json_object"},
                ),
                timeout=timeout_seconds,
            )
            last_error = None
            break
        except asyncio.TimeoutError as exc:
            last_error = exc
            logger.warning(
                "llm classifier timeout",
                extra={"channel": ctx.channel, "attempt": attempt + 1},
            )
        except Exception as exc:  # pragma: no cover - network/SDK exceptions
            last_error = exc
            logger.warning(
                "llm classifier failed: %s",
                exc,
                extra={"channel": ctx.channel, "attempt": attempt + 1},
            )

        if attempt + 1 < max_attempts:
            await asyncio.sleep(0.1)

    if response is None:
        error_label = "timeout" if isinstance(last_error, asyncio.TimeoutError) else "exception"
        return ClassificationResult(
            scenario=None,
            confidence=None,
            reason=error_label,
            error=str(last_error) if last_error else error_label,
            fallback=True,
        )

    choice = response.choices[0] if response.choices else None
    if not choice or not getattr(choice, "message", None):
        logger.warning("llm classifier returned empty message", extra={"channel": ctx.channel})
        return ClassificationResult(
            scenario=None,
            confidence=None,
            reason="empty_message",
            error="empty_message",
            fallback=True,
        )

    raw_content = _unwrap_content(choice.message.content)
    logger.info(
        "llm classifier raw response (channel=%s): %s",
        ctx.channel,
        raw_content,
    )

    try:
        parsed: Dict[str, Any] = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        logger.warning("llm classifier invalid json", extra={"channel": ctx.channel, "raw": raw_content[:200]})
        return ClassificationResult(
            scenario=None,
            confidence=None,
            reason="json_decode_error",
            error=str(exc),
            raw_response={"raw": raw_content},
            fallback=True,
        )

    scenario = parsed.get("scenario")
    if isinstance(scenario, str):
        scenario = scenario.strip() or None
    else:
        scenario = None

    confidence = parsed.get("confidence")
    try:
        confidence_value = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence_value = None

    reason = parsed.get("reason") if isinstance(parsed.get("reason"), str) else None

    tags = _normalize_tags(parsed.get("tags"))

    return ClassificationResult(
        scenario=scenario,
        confidence=confidence_value,
        reason=reason,
        tags=tags,
        raw_response=parsed,
    )
