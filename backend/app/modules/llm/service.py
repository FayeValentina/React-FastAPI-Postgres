"""
LLM service utilities: language-aware prompt construction and context wrapping.

Responsibilities:
- Detect input language (zh/en/ja; fallback en)
- Provide localized system_prompt
- When RAG context is available, wrap the user_text with localized instruction and the retrieved context
"""
from __future__ import annotations
from typing import Iterable, Tuple
from fastapi.concurrency import run_in_threadpool
try:
    from langdetect import detect  # type: ignore
except Exception:  # pragma: no cover - graceful fallback if not available
    detect = None  # type: ignore


SUPPORTED = {"en", "zh", "ja"}


def _normalize_lang(text: str) -> str:
    """Detect language and normalize to one of {en, zh, ja}; default 'en'."""
    lang = "en"
    if not text:
        return lang
    try:
        if detect is None:
            return lang
        raw = (detect(text) or "").lower()
        if raw.startswith("zh"):
            lang = "zh"
        elif raw.startswith("ja"):
            lang = "ja"
        elif raw.startswith("en"):
            lang = "en"
        else:
            lang = "en"
    except Exception:
        lang = "en"
    return lang


def _format_context(similar: Iterable[object]) -> str:
    """Join retrieved chunks into a single context block.

    Each item is expected to have a 'content' attribute; otherwise str(item) is used.
    """
    parts = []
    for c in similar or []:
        try:
            parts.append(getattr(c, "content", str(c)))
        except Exception:
            continue
    return "\n---\n".join([p for p in parts if p])


def _localized_prompts(lang: str) -> Tuple[str, str]:
    """Return (system_prompt, wrapper_template) for the language.

    wrapper_template expects two placeholders: {context} and {user_text}.
    """
    if lang == "zh":
        return (
            "你是一个乐于助人的助手。",
            "请参考以下资料回答问题，若资料不足请说明：\n{context}\n问题：{user_text}",
        )
    if lang == "ja":
        return (
            "あなたは役に立つアシスタントです。",
            "以下の情報を参考に質問に答えてください。不十分な場合はその旨を述べてください：\n{context}\n質問：{user_text}",
        )
    # default en
    return (
        "You are a helpful assistant.",
        "Please refer to the following information to answer the question. If the information is insufficient, please state so:\n{context}\nQuestion: {user_text}",
    )


def _prepare_system_and_user(
    user_text: str, similar: Iterable[object]
) -> Tuple[str, str]:
    """Build a localized system prompt and possibly wrapped user_text based on language.

    - Detect language from the original user_text.
    - If there is non-empty RAG context, wrap user_text with a localized instruction containing the context.
    - Return (system_prompt, final_user_text)
    """
    lang = _normalize_lang(user_text)
    system_prompt, template = _localized_prompts(lang)
    context = _format_context(similar)
    final_user = (
        template.format(context=context, user_text=user_text) if context else user_text
    )
    return system_prompt, final_user


async def prepare_system_and_user(
    user_text: str, similar: Iterable[object]
) -> Tuple[str, str]:
    """Async wrapper for `_prepare_system_and_user` for compatibility with async call sites."""
    return await run_in_threadpool(_prepare_system_and_user, user_text, similar)
