"""Prompt preparation utilities for the chat LLM endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Mapping, Tuple, TypeVar
from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.knowledge_base.language import detect_language
from app.modules.knowledge_base.retrieval import RetrievedChunk
from app.modules.llm import repository

@dataclass(frozen=True)
class PromptBundle:
    system: str
    context_template: str
    missing_template: str


def _normalize_lang(text: str) -> str:
    """Normalize language to {en, zh, ja} using shared KB heuristics."""
    normalized = (detect_language(text or "", default="en") or "en").lower()
    if normalized.startswith("zh"):
        return "zh"
    if normalized.startswith("ja"):
        return "ja"
    return "en"





def _build_context(
    similar: Iterable[RetrievedChunk],
    lang: str,
) -> str:
    max_items = max(1, settings.RAG_TOP_K)
    entries: List[str] = []

    for idx, item in enumerate(similar or [], start=1):
        if idx > max_items:
            break
        chunk = item.chunk
        content = (chunk.content or "").strip()
        if not content:
            continue
        chunk_lang = (chunk.language or lang).lower() if getattr(chunk, "language", None) else lang

        meta_parts: List[str] = []
        doc = getattr(chunk, "document", None)
        if doc and getattr(doc, "title", None):
            meta_parts.append(str(doc.title))
        if doc and getattr(doc, "source_ref", None):
            meta_parts.append(str(doc.source_ref))
        if chunk.chunk_index is not None:
            meta_parts.append(f"chunk #{chunk.chunk_index}")
        meta_parts.append(f"sim={item.similarity:.2f}")
        header = " | ".join(meta_parts)
        cite_key = f"CITE{idx}"
        entry = f"[{cite_key}] {header}\n{content}"

        entries.append(entry)
        if idx >= max_items:
            break

    return "\n\n".join(entries)


def _localized_prompts(lang: str) -> PromptBundle:
    if lang == "zh":
        return PromptBundle(
            system=(
                "你是一个严谨的助理。仅使用提供的证据回答问题，引用时使用 [CITEx] 形式。"
                "如果没有证据，请说明无法回答并请求补充信息，绝不能编造来源。"
            ),
            context_template=(
                "证据：\n{context}\n\n任务：\n"
                "1. 先给出 1-2 句总结。\n"
                "2. 使用条目列出关键步骤，并引用如 [CITE1]。\n"
                "3. 若证据不足，请明确指出不足之处。\n\n"
                "用户问题：\n{user_text}"
            ),
            missing_template=(
                "未检索到相关证据：\n{user_text}\n"
                "请告知用户当前没有匹配资料，并邀请其补充信息。"
            ),
        )
    if lang == "ja":
        return PromptBundle(
            system=(
                "あなたは精度を重視するアシスタントです。提供された証拠だけを使い、引用は [CITEx] の形式で行ってください。"
                "証拠がない場合は回答できないことを伝え、追加情報をお願いしてください。"
            ),
            context_template=(
                "証拠:\n{context}\n\nタスク:\n"
                "1. まず1〜2文で要約してください。\n"
                "2. 箇条書きで根拠を示し、[CITE1]のように引用してください。\n"
                "3. 証拠が不足している場合は、その旨を伝えてください。\n\n"
                "ユーザーの質問:\n{user_text}"
            ),
            missing_template=(
                "関連する証拠が見つかりませんでした:\n{user_text}\n"
                "その旨を説明し、追加情報を尋ねてください。"
            ),
        )

    return PromptBundle(
        system=(
            "You are a thorough assistant. Use ONLY the evidence provided. Cite supporting snippets using [CITEx]. "
            "If no evidence is available, explain that and ask the user for more information. Never fabricate sources."
        ),
        context_template=(
            "Evidence:\n{context}\n\nTask:\n"
            "1. Start with a concise 1-2 sentence summary.\n"
            "2. Provide bullet points with supporting details, citing like [CITE1].\n"
            "3. If the evidence is insufficient, clearly state what is missing.\n\n"
            "User Question:\n{user_text}"
        ),
        missing_template=(
            "No relevant evidence was found for the question below:\n{user_text}\n"
            "Let the user know you cannot answer with confidence and request clarification or more details."
        ),
    )


def _prepare_system_and_user(
    user_text: str,
    similar: Iterable[RetrievedChunk],
) -> Tuple[str, str]:
    """Build localized prompts together with formatted evidence and fallbacks."""

    lang = _normalize_lang(user_text)
    bundle = _localized_prompts(lang)
    evidence_list = list(similar or [])
    context = _build_context(evidence_list, lang) if evidence_list else ""

    if context:
        final_user = bundle.context_template.format(context=context, user_text=user_text)
    else:
        final_user = bundle.missing_template.format(user_text=user_text)

    return bundle.system, final_user


async def prepare_system_and_user(
    user_text: str,
    similar: Iterable[RetrievedChunk],
) -> Tuple[str, str]:
    """Async wrapper for `_prepare_system_and_user`."""

    return await run_in_threadpool(_prepare_system_and_user, user_text, similar)


async def delete_conversation(
    db: AsyncSession,
    *,
    conversation_id: UUID,
    user_id: int,
) -> bool:
    """Delete a conversation and cascade associated messages."""
    return await repository.delete_conversation(
        db,
        conversation_id=conversation_id,
        user_id=user_id,
    )
