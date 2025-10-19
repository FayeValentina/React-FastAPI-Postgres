from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple, TYPE_CHECKING

from app.core.config import settings
from app.modules.llm.client import classifier_client

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from ..llm.strategy import StrategyContext


logger = logging.getLogger(__name__)

ALLOWED_SCENARIOS = {"broad", "precise", "question", "document_focus", "unknown"}

MAX_REWRITTEN_CHARS = 600
MAX_REASON_WORDS = 60
MAX_REASON_CHARS = 320
MAX_TAGS = 5
MAX_TAG_LENGTH = 48
LOG_PREVIEW_CHARS = 512

def _to_snake_lower(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    # 替换非字母数字为下划线
    import re
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_")
    return s.lower()

def _clamp01(x: float | None) -> float | None:
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v < 0.0: 
        v = 0.0
    if v > 1.0: 
        v = 1.0
    # 保留两位小数（与提示词一致）
    return float(f"{v:.2f}")

def _sanitize_reason(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    words = text.split()
    if len(words) > MAX_REASON_WORDS:
        text = " ".join(words[:MAX_REASON_WORDS])
    if len(text) > MAX_REASON_CHARS:
        text = text[:MAX_REASON_CHARS].rstrip()
    return text or None

def _sanitize_rewritten_query(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) > MAX_REWRITTEN_CHARS:
        text = text[:MAX_REWRITTEN_CHARS].rstrip()
    return text


def _preview_text(value: Any, limit: int = LOG_PREVIEW_CHARS) -> str:
    if not isinstance(value, str):
        value = str(value)
    text = value.strip("\n")
    if len(text) <= limit:
        return text
    cutoff = max(1, limit - 1)
    return text[:cutoff].rstrip() + "…"


def _sanitize_parsed_payload(parsed: Dict[str, Any]) -> Dict[str, Any]:
    # scenario
    scenario = parsed.get("scenario")
    if isinstance(scenario, str):
        scenario = scenario.strip().lower()
    else:
        scenario = None
    if scenario not in ALLOWED_SCENARIOS:
        scenario = "unknown"

    # confidence
    confidence = parsed.get("confidence")
    confidence = _clamp01(confidence)
    # 如果未知场景，给一个较低置信度（与提示词一致的约束）
    if scenario == "unknown" and (confidence is None or confidence > 0.5):
        confidence = 0.5

    # reason （<=60 words）
    reason = _sanitize_reason(parsed.get("reason"))

    # tags （<=5，去重，小写 snake_case）
    norm = list(_normalize_tags(parsed.get("tags")))

    rewritten_query = _sanitize_rewritten_query(parsed.get("rewritten_query"))

    return {
        "scenario": scenario,
        "confidence": confidence,
        "reason": reason,
        "tags": norm,
        "rewritten_query": rewritten_query,
    }

PROMPT_TEMPLATE = (
    "You are a retrieval query processing assistant for a RAG system.\n"
    "Return a SINGLE compact JSON object ONLY, with EXACTLY these fields and no others:\n"
    "  - scenario: one of {broad, precise, question, document_focus, unknown}\n"
    "  - confidence: a float in [0,1], rounded to two decimals\n"
    "  - reason: <= 60 words, concise, in English\n"
    "  - tags: an array (0-5 items) of unique, lowercase strings (snake_case)\n"
    "  - rewritten_query: a richer retrieval-ready rewrite of the user's query in the SAME language, 1-3 sentences, <= 120 words\n"
    "\n"
    "Rewrite guidance:\n"
    "- Expand pronouns or vague references into explicit entities or actions.\n"
    "- Include relevant technical keywords, context, constraints, or desired outputs from the user query.\n"
    "- If the original query is already precise, you may return it unchanged.\n"
    "- Keep the rewrite factual and avoid fabricating details that contradict the query.\n"
    "\n"
    "Rules:\n"
    "1) Do not include any extra keys, comments, markdown, or prose outside the JSON object.\n"
    "2) If uncertain about intent, set scenario=\"unknown\" and confidence<=0.5 with a brief reason, but still provide your best rewrite.\n"
    "3) Never echo the entire payload or metadata fields.\n"
    "4) Preferred mapping hints (non-binding): broad=overviews/comparisons, precise=definitions or targeted instructions, question=Q&A/troubleshooting, document_focus=specific document or identifier.\n"
    "5) Keep tags topical (e.g., troubleshooting, procedural, compare, definition, api_usage), max 5, lowercase snake_case.\n"
    "\n"
    "Output format (shape only; values must reflect the input):\n"
    "{\"scenario\":\"precise\",\"confidence\":0.92,\"reason\":\"User requests a specific explanation with actionable focus.\",\"tags\":[\"definition\",\"procedural\"],\"rewritten_query\":\"Describe...\"}\n"
    "\n"
    "Few-shot calibration:\n"
    "USER: {\"query\":\"列出微服务最佳实践\",\"channel\":\"rest\"}\n"
    "ASSISTANT: {\"scenario\":\"broad\",\"confidence\":0.88,\"reason\":\"Asks for an overview of recommended actions.\",\"tags\":[\"overview\",\"best_practices\"],\"rewritten_query\":\"列出微服务架构在生产环境中的核心最佳实践，包括服务拆分、部署、监控、容错和团队协作指南。\"}\n"
    "\n"
    "USER: {\"query\":\"PostgreSQL 连接池超时怎么排查？\",\"channel\":\"rest\"}\n"
    "ASSISTANT: {\"scenario\":\"question\",\"confidence\":0.90,\"reason\":\"Troubleshooting intent with a clear problem.\",\"tags\":[\"troubleshooting\",\"database\"],\"rewritten_query\":\"提供排查 PostgreSQL 生产环境连接池超时问题的步骤，重点涵盖常见错误日志、max_connections、statement_timeout 设置以及连接池监控指标。\"}\n"
    "\n"
    "USER: {\"query\":\"12-factor 中的端口绑定要点\",\"channel\":\"websocket\"}\n"
    "ASSISTANT: {\"scenario\":\"precise\",\"confidence\":0.93,\"reason\":\"Specific concept explanation with focused scope.\",\"tags\":[\"definition\"],\"rewritten_query\":\"解释 12-factor 应用中 Port Binding 原则的关键要点，包括应用如何独立绑定端口、避免依赖外部 web 服务器，以及在部署中的实践示例。\"}\n"
)



@dataclass(slots=True)
class ClassificationResult:
    scenario: str | None
    confidence: float | None
    reason: str | None
    tags: Tuple[str, ...] = ()
    rewritten_query: str | None = None
    raw_response: Dict[str, Any] | None = None
    request_payload: Dict[str, Any] | None = None
    parsed_response: Dict[str, Any] | None = None
    sanitized_response: Dict[str, Any] | None = None
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
        if self.rewritten_query:
            preview = self.rewritten_query
            if len(preview) > 160:
                preview = preview[:157].rstrip() + "…"
            payload["rewritten_query"] = preview
        if self.sanitized_response:
            payload["sanitized_keys"] = sorted(self.sanitized_response.keys())
        if self.request_payload:
            payload["request_payload_keys"] = sorted(self.request_payload.keys())
        if self.fallback:
            payload["fallback"] = True
        if self.error:
            payload["error"] = self.error
        return payload

    def to_payload(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario,
            "confidence": self.confidence,
            "reason": self.reason,
            "tags": list(self.tags),
            "rewritten_query": self.rewritten_query,
            "raw_response": self.raw_response,
            "request_payload": self.request_payload,
            "parsed_response": self.parsed_response,
            "sanitized_response": self.sanitized_response,
            "source": self.source,
            "fallback": self.fallback,
            "error": self.error,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ClassificationResult":
        tags_value = payload.get("tags")
        if isinstance(tags_value, str):
            tags_tuple = (tags_value,)
        elif isinstance(tags_value, Iterable):
            tags_tuple = tuple(str(item) for item in tags_value if isinstance(item, str))
        else:
            tags_tuple = ()

        confidence_value: float | None = None
        if payload.get("confidence") is not None:
            try:
                confidence_value = float(payload.get("confidence"))
            except (TypeError, ValueError):
                confidence_value = None

        return cls(
            scenario=str(payload["scenario"]) if payload.get("scenario") is not None else None,
            confidence=confidence_value,
            reason=str(payload["reason"]) if payload.get("reason") is not None else None,
            tags=tags_tuple,
            rewritten_query=str(payload["rewritten_query"]) if payload.get("rewritten_query") is not None else None,
            raw_response=payload.get("raw_response") if isinstance(payload.get("raw_response"), dict) else None,
            request_payload=payload.get("request_payload") if isinstance(payload.get("request_payload"), dict) else None,
            parsed_response=payload.get("parsed_response") if isinstance(payload.get("parsed_response"), dict) else None,
            sanitized_response=payload.get("sanitized_response") if isinstance(payload.get("sanitized_response"), dict) else None,
            source=str(payload["source"]) if payload.get("source") is not None else "llm",
            fallback=bool(payload.get("fallback", False)),
            error=str(payload["error"]) if payload.get("error") is not None else None,
        )


def _normalize_tags(raw: Any) -> Tuple[str, ...]:
    candidates: list[str] = []
    if isinstance(raw, str):
        stripped = raw.strip()
        if stripped:
            candidates.append(stripped)
    elif isinstance(raw, Iterable):
        for item in raw:
            if isinstance(item, str):
                stripped = item.strip()
                if stripped:
                    candidates.append(stripped)

    normalized: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        tag = _to_snake_lower(candidate)
        if not tag:
            continue
        if len(tag) > MAX_TAG_LENGTH:
            tag = tag[:MAX_TAG_LENGTH]
        if tag in seen:
            continue
        normalized.append(tag)
        seen.add(tag)
        if len(normalized) >= MAX_TAGS:
            break
    return tuple(normalized)


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

    response = None
    last_error: Optional[BaseException] = None
    max_attempts = 2

    for attempt in range(max_attempts):
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
            raw_response={"error": error_label},
            request_payload=payload,
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
            request_payload=payload,
            fallback=True,
        )

    raw_content = _unwrap_content(choice.message.content)
    raw_preview = _preview_text(raw_content, LOG_PREVIEW_CHARS)
    logger.info(
        "llm classifier raw response (channel=%s): %s",
        ctx.channel,
        raw_preview,
    )
    
    try:
        logger.debug(
            "llm classifier full response (channel=%s): %s",
            ctx.channel,
            response.model_dump_json(indent=2)
        )
    except Exception:
        logger.debug(
            "llm classifier full response (channel=%s) [fallback str]: %s",
            ctx.channel,
            json.dumps(getattr(response, "__dict__", str(response)), ensure_ascii=False)[:4000],
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
            raw_response={"raw": _preview_text(raw_content)},
            request_payload=payload,
            fallback=True,
        )

    sanitized = _sanitize_parsed_payload(parsed)

    scenario = sanitized["scenario"]
    confidence_value = sanitized["confidence"]
    reason = sanitized["reason"]
    tags = tuple(sanitized["tags"])
    rewritten_query = sanitized["rewritten_query"]

    return ClassificationResult(
        scenario=scenario,
        confidence=confidence_value,
        reason=reason,
        tags=tags,
        rewritten_query=rewritten_query,
        raw_response={
            "raw": raw_preview,
            "parsed": parsed,
            "sanitized": sanitized,
        },
        request_payload=payload,
        parsed_response=parsed,
        sanitized_response=sanitized,
    )
