from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence, TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.llm.client import classifier_client
from app.modules.llm.intent_classifier import ClassificationResult
from app.modules.llm import repository

try:  # pragma: no cover - optional dependency
    from langdetect import detect  # type: ignore
except Exception:  # pragma: no cover - graceful fallback when unavailable
    detect = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover - typing aid
    from app.modules.llm.models import Message


logger = logging.getLogger(__name__)

MAX_MESSAGES_FOR_METADATA = 12
MAX_MESSAGE_CHARS = 420
MAX_TRANSCRIPT_CHARS = 3200
MAX_TITLE_CHARS = 80
MAX_SUMMARY_CHARS = 480
LOG_PREVIEW_CHARS = 512
REQUEST_TIMEOUT_SECONDS = 30

LANGUAGE_LABELS = {
    "en": "English",
    "zh": "Chinese",
    "ja": "Japanese",
}

SYSTEM_PROMPT_TEMPLATES: Dict[str, str] = {
    "question_troubleshooting": (
        "You are an expert troubleshooting assistant. Ask for missing details, reason step-by-step, "
        "and provide actionable fixes grounded in verified knowledge."
    ),
    "precise_instruction": (
        "You are a concise technical assistant. Provide exact instructions or factual answers with clear steps "
        "or code snippets when helpful."
    ),
    "broad_overview": (
        "You deliver high-level overviews and comparisons. Summarize key points, highlight trade-offs, "
        "and keep explanations accessible."
    ),
    "document_focus": (
        "Act as a retrieval-grounded assistant. Only reference the supplied document(s); cite relevant sections "
        "and avoid fabricating external facts."
    ),
    "analysis_reasoning": (
        "You are a critical analyst. Decompose problems, evaluate alternatives, and explain your reasoning "
        "transparently before concluding."
    ),
    "coding_help": (
        "You are a senior software engineer. Produce idiomatic, well-commented code, explain the approach, "
        "and point out potential pitfalls or tests."
    ),
    "brainstorming": (
        "You are a creative collaborator. Generate diverse, high-quality ideas, explore variations, "
        "and note constraints or next steps."
    ),
    "translation_localization": (
        "You are a professional translator. Preserve meaning, tone, and domain-specific terminology while "
        "adapting content to the target locale."
    ),
    "unknown_fallback": (
        "Default to a helpful AI assistant. Clarify the user’s intent when needed and keep responses accurate, "
        "polite, and safe."
    ),
}


@lru_cache(maxsize=1)
def _get_system_prompt_templates() -> Dict[str, str]:
    templates = dict(SYSTEM_PROMPT_TEMPLATES)
    overrides = getattr(settings, "CONVERSATION_SYSTEM_PROMPT_OVERRIDES", None)
    if isinstance(overrides, dict):
        for key, value in overrides.items():
            if not isinstance(key, str) or not isinstance(value, str):
                continue
            normalized_key = key.strip()
            normalized_value = value.strip()
            if not normalized_key or not normalized_value:
                continue
            templates[normalized_key] = normalized_value
    return templates

TAG_PROMPT_MAP: Dict[str, str] = {
    "troubleshooting": "question_troubleshooting",
    "incident": "question_troubleshooting",
    "diagnostics": "question_troubleshooting",
    "compare": "broad_overview",
    "overview": "broad_overview",
    "summary": "broad_overview",
    "procedural": "precise_instruction",
    "precise": "precise_instruction",
    "definition": "precise_instruction",
    "document_focus": "document_focus",
    "document": "document_focus",
    "analysis": "analysis_reasoning",
    "root_cause": "analysis_reasoning",
    "code": "coding_help",
    "coding": "coding_help",
    "api_usage": "coding_help",
    "refactor": "coding_help",
    "brainstorm": "brainstorming",
    "creative": "brainstorming",
    "ideas": "brainstorming",
    "translation": "translation_localization",
    "localization": "translation_localization",
}

SCENARIO_PROMPT_MAP: Dict[str, str] = {
    "question": "question_troubleshooting",
    "document_focus": "document_focus",
    "broad": "broad_overview",
    "precise": "precise_instruction",
    "analysis": "analysis_reasoning",
}

METADATA_SYSTEM_PROMPT = (
    "You generate metadata for chat conversations.\n"
    f"Return a SINGLE JSON object with EXACTLY these keys: title, summary.\n"
    f"- title: <= {MAX_TITLE_CHARS} characters, specific, no quotes, same language as `language_label`.\n"
    f"- summary: <= {MAX_SUMMARY_CHARS} characters, concise, at most 2 sentences, same language as `language_label`.\n"
    "Do not output markdown, explanations, or extra keys."
)


@dataclass(slots=True)
class ConversationMetadataUpdate:
    title: str
    summary: Optional[str]
    system_prompt: str
    language: str
    raw_response: Optional[Dict[str, Any]] = None


def _truncate(text: str, limit: int) -> str:
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    cutoff = max(1, limit - 1)
    return stripped[:cutoff].rstrip() + "…"


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_language_code(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if value.startswith("zh"):
        return "zh"
    if value.startswith("ja"):
        return "ja"
    if value.startswith("en"):
        return "en"
    return "en"


def _detect_language(messages: Sequence["Message"], classifier_result: ClassificationResult) -> str:
    candidates: List[str] = []

    for message in reversed(messages):
        if message.role == "user" and message.content:
            candidates.append(message.content)
            if len(candidates) >= 2:
                break

    if not candidates and classifier_result.rewritten_query:
        candidates.append(classifier_result.rewritten_query)

    request_payload = classifier_result.request_payload or {}
    query_text = request_payload.get("query")
    if isinstance(query_text, str) and query_text.strip():
        candidates.append(query_text)

    for message in reversed(messages):
        if message.content:
            candidates.append(message.content)
            if len(candidates) >= 4:
                break

    if detect is None:
        return "en"

    for text in candidates:
        try:
            sample = text[:512] if len(text) > 512 else text
            language = detect(sample)
        except Exception:
            continue
        normalized = _normalize_language_code(language)
        if normalized in LANGUAGE_LABELS:
            return normalized
    return "en"


def _format_transcript(messages: Sequence["Message"]) -> str:
    lines: List[str] = []
    total_chars = 0

    for message in messages:
        if message.role not in {"user", "assistant"}:
            continue
        content = (message.content or "").strip()
        if not content:
            continue
        normalized = _normalize_whitespace(content)
        snippet = _truncate(normalized, MAX_MESSAGE_CHARS)
        role = message.role.upper()
        entry = f"{role}: {snippet}"
        entry_length = len(entry)
        if total_chars + entry_length > MAX_TRANSCRIPT_CHARS and lines:
            break
        total_chars += entry_length
        lines.append(entry)

    if not lines:
        return ""
    return "\n".join(lines)


def _sanitize_title(value: Any, language: str, fallback: str) -> str:
    if isinstance(value, str):
        candidate = _normalize_whitespace(value)
    else:
        candidate = ""

    if not candidate:
        candidate = fallback
    candidate = _truncate(candidate, MAX_TITLE_CHARS)

    if not candidate:
        candidate = fallback or "New Chat"

    return candidate


def _sanitize_summary(value: Any, language: str) -> Optional[str]:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    candidate = re.sub(r"\s+", " ", candidate)
    candidate = _truncate(candidate, MAX_SUMMARY_CHARS)
    return candidate or None


def _fallback_title(messages: Sequence["Message"]) -> str:
    for message in reversed(messages):
        if message.role != "user":
            continue
        content = _normalize_whitespace(message.content or "")
        if content:
            return _truncate(content, MAX_TITLE_CHARS)
    return "New Chat"


def _preview_text(value: Any, limit: int = LOG_PREVIEW_CHARS) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = text.replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    cutoff = max(1, limit - 1)
    return text[:cutoff].rstrip() + "…"


def _unwrap_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        pieces: List[str] = []
        for item in content:
            if isinstance(item, str):
                pieces.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    pieces.append(text)
        return "".join(pieces)
    return str(content or "")


def _select_system_prompt(result: ClassificationResult) -> str:
    templates = _get_system_prompt_templates()
    tags = [tag.lower() for tag in result.tags]
    for tag in tags:
        template_key = TAG_PROMPT_MAP.get(tag)
        if template_key:
            candidate = templates.get(template_key)
            if candidate:
                return candidate

    scenario = (result.scenario or "").lower()
    template_key = SCENARIO_PROMPT_MAP.get(scenario)
    if template_key:
        candidate = templates.get(template_key)
        if candidate:
            return candidate

    return templates.get("unknown_fallback", SYSTEM_PROMPT_TEMPLATES["unknown_fallback"])


async def _call_metadata_model(payload: Dict[str, Any]) -> Dict[str, Any] | None:
    try:
        response = await asyncio.wait_for(
            classifier_client.chat.completions.create(
                model=settings.CLASSIFIER_MODEL,
                messages=[
                    {"role": "system", "content": METADATA_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                temperature=0.0,
                top_p=0.0,
                max_tokens=256,
                response_format={"type": "json_object"},
            ),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning("conversation metadata model timed out")
        return None
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("conversation metadata model failed: %s", exc)
        return None

    choice = response.choices[0] if response.choices else None
    if not choice or not getattr(choice, "message", None):
        logger.warning("conversation metadata model returned empty content")
        return None

    raw_content = _unwrap_message_content(choice.message.content)
    preview = _preview_text(raw_content)
    logger.info("conversation metadata raw response: %s", preview)

    transcript_preview = _preview_text(payload.get("transcript", ""))
    logger.debug(
        "conversation metadata payload summary: language=%s scenario=%s tags=%s transcript=%s",
        payload.get("language_code"),
        payload.get("classifier", {}).get("scenario"),
        payload.get("classifier", {}).get("tags"),
        transcript_preview,
    )

    try:
        parsed = json.loads(raw_content) if isinstance(raw_content, str) else dict(raw_content or {})
    except Exception as exc:
        logger.warning("conversation metadata invalid json: %s", exc)
        return None

    if not isinstance(parsed, dict):
        logger.warning("conversation metadata response not a JSON object")
        return None
    return parsed


async def generate_conversation_metadata(
    db: AsyncSession,
    *,
    conversation_id: UUID,
    classifier_result: ClassificationResult,
    message_limit: int = MAX_MESSAGES_FOR_METADATA,
) -> ConversationMetadataUpdate | None:
    messages = await repository.get_recent_messages(
        db,
        conversation_id=conversation_id,
        limit=message_limit,
    )

    transcript = _format_transcript(messages)
    if not transcript and not classifier_result.rewritten_query:
        logger.debug("conversation metadata skipped: empty transcript and no rewritten query")
        return None

    language_code = _detect_language(messages, classifier_result)
    language_label = LANGUAGE_LABELS.get(language_code, "English")

    classifier_payload = {
        "scenario": classifier_result.scenario or "unknown",
        "tags": list(classifier_result.tags),
        "confidence": classifier_result.confidence,
        "reason": classifier_result.reason,
        "rewritten_query": classifier_result.rewritten_query,
    }

    request_payload = {
        "language_code": language_code,
        "language_label": language_label,
        "classifier": classifier_payload,
        "transcript": transcript,
    }

    logger.debug(
        "conversation metadata request prepared: conversation_id=%s language=%s scenario=%s tags=%s",
        conversation_id,
        language_code,
        classifier_payload["scenario"],
        classifier_payload["tags"],
    )

    parsed = await _call_metadata_model(request_payload)
    if parsed is None:
        return None

    fallback_title = _fallback_title(messages) or "New Chat"
    title = _sanitize_title(parsed.get("title"), language_code, fallback_title)
    summary = _sanitize_summary(parsed.get("summary"), language_code)
    system_prompt = _select_system_prompt(classifier_result)

    raw_response = {"parsed": parsed}

    logger.debug(
        "conversation metadata generated: title=%s summary_preview=%s language=%s",
        title,
        _preview_text(summary or ""),
        language_code,
    )

    return ConversationMetadataUpdate(
        title=title,
        summary=summary,
        system_prompt=system_prompt,
        language=language_code,
        raw_response=raw_response,
    )
