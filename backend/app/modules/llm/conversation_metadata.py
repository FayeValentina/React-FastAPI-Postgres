"""Conversation metadata generation utilities.
对话元数据生成工具。
"""

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
from app.modules.llm.intent_classifier import RouterDecision
from app.modules.llm import repository
from app.modules.knowledge_base.language import detect_language

if TYPE_CHECKING:  # pragma: no cover - typing aid
    from app.modules.llm.models import Message


logger = logging.getLogger(__name__)

# 元数据生成的相关限制常量
MAX_MESSAGES_FOR_METADATA = 12
MAX_MESSAGE_CHARS = 420
MAX_TRANSCRIPT_CHARS = 3200
MAX_TITLE_CHARS = 80
MAX_SUMMARY_CHARS = 480
LOG_PREVIEW_CHARS = 512
REQUEST_TIMEOUT_SECONDS = 300

# 语言标签映射
LANGUAGE_LABELS = {
    "en": "English",
    "zh": "Chinese",
    "ja": "Japanese",
}

# 系统提示模板
SYSTEM_PROMPT_TEMPLATES: Dict[str, str] = {
    "document_focus": (
        "Act as a retrieval-grounded assistant. Only reference the supplied document(s); cite relevant sections "
        "and avoid fabricating external facts."
    ),
    "unknown_fallback": (
        "Default to a helpful AI assistant. Clarify the user’s intent when needed and keep responses accurate, "
        "polite, and safe."
    ),
}


@lru_cache(maxsize=1)
def _get_system_prompt_templates() -> Dict[str, str]:
    """Get system prompt templates, allowing overrides from settings.
    获取系统提示模板，允许从设置中覆盖。
    """
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


# 用于生成元数据的系统提示
METADATA_SYSTEM_PROMPT = (
    "You generate metadata for chat conversations.\n"
    f"Return a SINGLE JSON object with EXACTLY these keys: title, summary.\n"
    f"- title: <= {MAX_TITLE_CHARS} characters, specific, no quotes, same language as `language_label`.\n"
    f"- summary: <= {MAX_SUMMARY_CHARS} characters, concise, at most 2 sentences, same language as `language_label`.\n"
    "Do not output markdown, explanations, or extra keys."
)


@dataclass(slots=True)
class ConversationMetadataUpdate:
    """Container for updated conversation metadata.
    更新后的对话元数据容器。
    """
    title: str  # 对话标题
    summary: Optional[str]  # 对话摘要
    system_prompt: str  # 系统提示词
    language: str  # 对话语言
    raw_response: Optional[Dict[str, Any]] = None  # 原始响应数据


def _truncate(text: str, limit: int) -> str:
    """Truncate text to a maximum length, adding ellipsis if needed.
    将文本截断到最大长度，如果需要则添加省略号。
    """
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    cutoff = max(1, limit - 1)
    return stripped[:cutoff].rstrip() + "…"


def _normalize_whitespace(text: str) -> str:
    """Collapse multiple whitespace characters into a single space.
    将多个空白字符合并为单个空格。
    """
    return re.sub(r"\s+", " ", text).strip()

def _detect_language(messages: Sequence["Message"], classifier_result: RouterDecision) -> str:
    """Detect the dominant language of the conversation.
    检测对话的主要语言。
    """
    candidates: List[str] = []

    # 优先检查最近的用户消息
    for message in reversed(messages):
        if message.role == "user" and message.content:
            candidates.append(message.content)
            if len(candidates) >= 2:
                break

    # 检查分类器结果中的搜索查询
    if not candidates and classifier_result.search_query:
        candidates.append(classifier_result.search_query)

    # 检查请求负载中的查询
    request_payload = classifier_result.request_payload or {}
    query_text = request_payload.get("query")
    if isinstance(query_text, str) and query_text.strip():
        candidates.append(query_text)

    # 检查更多历史消息
    for message in reversed(messages):
        if message.content:
            candidates.append(message.content)
            if len(candidates) >= 4:
                break

    # 对候选文本进行语言检测
    for text in candidates:
        detected = (detect_language(text, default="en") or "en").lower()
        if detected == "code":
            detected = "en"
        if detected.startswith("zh"):
            return "zh"
        if detected.startswith("ja"):
            return "ja"
        if detected.startswith("en"):
            return "en"

    return "en"


def _format_transcript(messages: Sequence["Message"]) -> str:
    """Format conversation history into a transcript string.
    将对话历史格式化为转录字符串。
    """
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
    """Sanitize and validate the generated title.
    清理并验证生成的标题。
    """
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
    """Sanitize and validate the generated summary.
    清理并验证生成的摘要。
    """
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    candidate = re.sub(r"\s+", " ", candidate)
    candidate = _truncate(candidate, MAX_SUMMARY_CHARS)
    return candidate or None


def _fallback_title(messages: Sequence["Message"]) -> str:
    """Generate a fallback title from the last user message.
    从最后一条用户消息生成回退标题。
    """
    for message in reversed(messages):
        if message.role != "user":
            continue
        content = _normalize_whitespace(message.content or "")
        if content:
            return _truncate(content, MAX_TITLE_CHARS)
    return "New Chat"


def _preview_text(value: Any, limit: int = LOG_PREVIEW_CHARS) -> str:
    """Create a short preview of text for logging.
    为日志记录创建文本的简短预览。
    """
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = text.replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    cutoff = max(1, limit - 1)
    return text[:cutoff].rstrip() + "…"


def _unwrap_message_content(content: Any) -> str:
    """Extract string content from various message formats.
    从各种消息格式中提取字符串内容。
    """
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


def _select_system_prompt(result: RouterDecision) -> str:
    """Select appropriate system prompt based on router decision.
    根据路由决策选择合适的系统提示。
    """
    templates = _get_system_prompt_templates()
    if result.mode == "search":
        return templates.get("document_focus", SYSTEM_PROMPT_TEMPLATES["document_focus"])
    return templates.get("unknown_fallback", SYSTEM_PROMPT_TEMPLATES["unknown_fallback"])


async def _call_metadata_model(payload: Dict[str, Any]) -> Dict[str, Any] | None:
    """Call the LLM to generate metadata.
    调用 LLM 生成元数据。
    
    此函数负责：
    1. 构造 LLM 请求，包含系统提示和用户提供的 payload（转录内容等）。
    2. 设置请求参数（如 temperature=0.0 以获得确定性输出）。
    3. 处理可能的超时和异常。
    4. 解析返回的 JSON 内容并进行基本的验证。
    """
    try:
        # 发送请求给分类器模型，设置超时时间
        response = await asyncio.wait_for(
            classifier_client.chat.completions.create(
                model=settings.CLASSIFIER_MODEL,
                messages=[
                    {"role": "system", "content": METADATA_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                temperature=0.0,  # 使用 0 温度以获得更稳定的输出
                top_p=0.0,
                max_tokens=256,
                response_format={"type": "json_object"},  # 强制模型返回 JSON 对象
            ),
            timeout=REQUEST_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        logger.warning("conversation metadata model timed out")
        return None
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("conversation metadata model failed: %s", exc)
        return None

    # 提取响应内容
    choice = response.choices[0] if response.choices else None
    if not choice or not getattr(choice, "message", None):
        logger.warning("conversation metadata model returned empty content")
        return None

    raw_content = _unwrap_message_content(choice.message.content)
    preview = _preview_text(raw_content)
    logger.info("conversation metadata raw response: %s", preview)

    # 记录 payload 摘要以便调试
    transcript_preview = _preview_text(payload.get("transcript", ""))
    logger.debug(
        "conversation metadata payload summary: language=%s scenario=%s tags=%s transcript=%s",
        payload.get("language_code"),
        payload.get("router", {}).get("mode"),
        payload.get("router", {}).get("reason"),
        transcript_preview,
    )

    try:
        # 解析 JSON 响应
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
    classifier_result: RouterDecision,
    message_limit: int = MAX_MESSAGES_FOR_METADATA,
) -> ConversationMetadataUpdate | None:
    """Generate metadata (title, summary, etc.) for a conversation.
    为对话生成元数据（标题、摘要等）。
    
    主要流程：
    1. 获取最近的对话消息。
    2. 将消息格式化为转录文本。
    3. 检测对话语言。
    4. 准备请求 payload，包含路由信息和转录文本。
    5. 调用 LLM 生成元数据。
    6. 清理和验证生成的标题和摘要。
    7. 根据路由结果选择合适的系统提示词。
    """
    # 1. 获取最近的消息
    messages = await repository.get_recent_messages(
        db,
        conversation_id=conversation_id,
        limit=message_limit,
    )

    # 2. 格式化转录文本
    transcript = _format_transcript(messages)
    # 如果没有转录内容且没有搜索查询，则跳过生成
    if not transcript and not classifier_result.search_query:
        logger.debug("conversation metadata skipped: empty transcript and no rewritten query")
        return None

    # 3. 检测语言
    language_code = _detect_language(messages, classifier_result)
    language_label = LANGUAGE_LABELS.get(language_code, "English")

    # 4. 准备请求 payload
    router_payload = {
        "mode": classifier_result.mode,
        "reason": classifier_result.reason,
        "search_query": classifier_result.search_query,
    }

    request_payload = {
        "language_code": language_code,
        "language_label": language_label,
        "router": router_payload,
        "transcript": transcript,
    }

    logger.debug(
        "conversation metadata request prepared: conversation_id=%s language=%s mode=%s",
        conversation_id,
        language_code,
        router_payload["mode"],
    )

    # 5. 调用 LLM
    parsed = await _call_metadata_model(request_payload)
    if parsed is None:
        return None

    # 6. 清理和验证结果
    fallback_title = _fallback_title(messages) or "New Chat"
    title = _sanitize_title(parsed.get("title"), language_code, fallback_title)
    summary = _sanitize_summary(parsed.get("summary"), language_code)
    
    # 7. 选择系统提示词
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
