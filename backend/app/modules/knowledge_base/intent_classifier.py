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

ALLOWED_SCENARIOS = {"broad", "precise", "question", "document_focus", "unknown"}

MAX_REWRITTEN_CHARS = 600

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

def _limit_words(reason: str | None, max_words: int = 60) -> str | None:
    if not isinstance(reason, str):
        return None
    words = reason.strip().split()
    if len(words) <= max_words:
        return reason.strip()
    return " ".join(words[:max_words]).strip()

def _sanitize_rewritten_query(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) > MAX_REWRITTEN_CHARS:
        text = text[:MAX_REWRITTEN_CHARS].rstrip()
    return text


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
    reason = parsed.get("reason") if isinstance(parsed.get("reason"), str) else None
    reason = _limit_words(reason, 60)

    # tags （<=5，去重，小写 snake_case）
    raw_tags = parsed.get("tags")
    tags_tuple = _normalize_tags(raw_tags)  # 你现有的：支持 str 或 Iterable
    norm = []
    seen = set()
    for t in tags_tuple:
        tt = _to_snake_lower(t)
        if tt and tt not in seen:
            norm.append(tt)
            seen.add(tt)
        if len(norm) >= 5:
            break

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
            raw_response={"raw": raw_content},
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
        raw_response={"parsed": parsed, "sanitized": sanitized},
    )
