from __future__ import annotations

from typing import Any, Callable, Iterable, List, Mapping, Optional, TypeVar
from functools import lru_cache
from dataclasses import dataclass
import os
import math
import re
import logging
from collections import defaultdict

import numpy as np

from sentence_transformers import SentenceTransformer
from fastapi.concurrency import run_in_threadpool
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infrastructure.dynamic_settings import DynamicSettingsService
from . import models
from .repository import crud_knowledge_base
from markdown import markdown
from bs4 import BeautifulSoup


# 嵌入模型（CPU 上加载，保持与 DB 维度一致）
_model = SentenceTransformer(settings.EMBEDDING_MODEL)


@dataclass(slots=True)
class SplitChunk:
    content: str
    language: str | None
    is_code: bool = False


@dataclass(slots=True)
class RetrievedChunk:
    chunk: "models.KnowledgeChunk"
    distance: float
    similarity: float
    score: float
    embedding: np.ndarray
    mmr_score: float = 0.0


logger = logging.getLogger(__name__)

T = TypeVar("T")
DynamicSettingsMapping = Mapping[str, Any]


def _coerce_config_value(
    config: DynamicSettingsMapping | None,
    key: str,
    default: T,
    caster: Callable[[Any], T],
) -> T:
    """Retrieve a config value and coerce it to the expected type with fallback."""
    source = default if config is None else config.get(key, default)
    try:
        return caster(source)
    except (TypeError, ValueError):
        return caster(default)


async def _resolve_dynamic_settings(
    service: DynamicSettingsService | None,
) -> dict[str, Any]:
    """Fetch dynamic settings via the service or fall back to static defaults."""
    if service is None:
        return settings.dynamic_settings_defaults()

    payload = await service.get_all()
    if not isinstance(payload, dict):  # defensive guard
        logger.warning("Dynamic settings service returned non-dict payload; using defaults")
        return settings.dynamic_settings_defaults()
    return payload


try:
    from langdetect import detect as _langdetect_detect  # type: ignore
except Exception:  # pragma: no cover - best effort language detection
    _langdetect_detect = None  # type: ignore


def _detect_language(text: str, default: str = "en") -> str:
    """Best-effort language detection normalized to zh/en/ja fallback en."""
    if not text or not text.strip():
        return default
    try:
        if _langdetect_detect is None:
            return default
        raw = (_langdetect_detect(text) or "").lower()
    except Exception:
        return default

    if raw.startswith("zh"):
        return "zh"
    if raw.startswith("ja"):
        return "ja"
    if raw.startswith("en"):
        return "en"
    return default


TEXT_MIME_TYPES = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "text/tab-separated-values",
    "application/json",
    "application/xml",
    "application/yaml",
    "application/x-yaml",
}

TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".tsv",
    ".json",
    ".yaml",
    ".yml",
}


def _allowed_text_mime(content_type: Optional[str]) -> bool:
    if not content_type:
        return False
    ctype = content_type.split(";", 1)[0].strip().lower()
    return ctype in TEXT_MIME_TYPES or ctype.startswith("text/")


def _allowed_text_suffix(filename: Optional[str]) -> bool:
    if not filename:
        return False
    suffix = os.path.splitext(filename)[1].lower()
    return suffix in TEXT_EXTENSIONS


def _decode_bytes_to_text(raw: bytes, encodings: Iterable[str] = ("utf-8", "utf-8-sig", "gbk")) -> str:
    if not raw:
        return ""
    for encoding in encodings:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def _mmr_select(
    candidates: List[RetrievedChunk],
    top_k: int,
    mmr_lambda: float,
    per_doc_limit: int,
) -> List[RetrievedChunk]:
    if top_k <= 0:
        return []
    selected: List[RetrievedChunk] = []
    remaining = candidates.copy()
    doc_counts: defaultdict[int | None, int] = defaultdict(int)

    while remaining and len(selected) < top_k:
        best_index = None
        best_score = float("-inf")
        for idx, candidate in enumerate(remaining):
            doc_id = candidate.chunk.document_id
            if doc_id is not None and per_doc_limit > 0 and doc_counts[doc_id] >= per_doc_limit:
                continue

            if not selected:
                mmr_score = candidate.score
            else:
                redundancy = max(
                    float(np.dot(candidate.embedding, chosen.embedding))
                    for chosen in selected
                )
                mmr_score = mmr_lambda * candidate.score - (1 - mmr_lambda) * redundancy

            if mmr_score > best_score:
                best_score = mmr_score
                best_index = idx

        if best_index is None:
            break

        chosen = remaining.pop(best_index)
        chosen.mmr_score = best_score
        selected.append(chosen)
        doc_id = chosen.chunk.document_id
        if doc_id is not None and per_doc_limit > 0:
            doc_counts[doc_id] += 1

    return selected


def _estimate_tokens(text: str, lang: str | None, is_code: bool = False) -> int:
    if not text:
        return 0
    if is_code:
        return max(1, len(text.splitlines()) * 3)
    lang = (lang or "en").lower()
    stripped = text.strip()
    if not stripped:
        return 0
    if lang == "en":
        return max(1, len(stripped.split()))
    if lang in {"zh", "ja"}:
        return max(1, len(stripped))
    return max(1, math.ceil(len(stripped) / 4))


def _chunk_target_tokens_for_lang(
    lang: str | None,
    config: DynamicSettingsMapping | None,
) -> int:
    lang_code = (lang or "en").lower()
    if lang_code == "en":
        return _coerce_config_value(
            config,
            "RAG_CHUNK_TARGET_TOKENS_EN",
            settings.RAG_CHUNK_TARGET_TOKENS_EN,
            int,
        )
    if lang_code in {"zh", "ja"}:
        return _coerce_config_value(
            config,
            "RAG_CHUNK_TARGET_TOKENS_CJK",
            settings.RAG_CHUNK_TARGET_TOKENS_CJK,
            int,
        )
    return _coerce_config_value(
        config,
        "RAG_CHUNK_TARGET_TOKENS_DEFAULT",
        settings.RAG_CHUNK_TARGET_TOKENS_DEFAULT,
        int,
    )


def _segment_sentences(text: str, lang: str) -> List[str]:
    if not text:
        return []
    lang = (lang or "en").lower()
    if lang == "en":
        nlp = _get_spacy_nlp_for_lang("en")
        if nlp is not None:
            try:
                doc = nlp(text)
                sentences = [s.text.strip() for s in getattr(doc, "sents", []) if s.text.strip()]
                if sentences:
                    return sentences
            except Exception:
                sentences = []
        # fallback: punctuation splitting
        sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
        return [s.strip() for s in sentences if s and s.strip()]

    if lang in {"zh", "ja"}:
        sentences = re.split(r"[。！？!?]+|\n+", text)
        return [s.strip() for s in sentences if s and s.strip()]

    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [s.strip() for s in sentences if s and s.strip()]


def _join_sentences(sentences: List[str], lang: str) -> str:
    if not sentences:
        return ""
    lang = (lang or "en").lower()
    if lang == "en":
        return " ".join(sentences).strip()
    if lang in {"zh", "ja"}:
        return "".join(sentences).strip()
    return "\n".join(sentences).strip()


def _pack_sentences(sentences: List[str], lang: str, target_tokens: int, overlap_tokens: int) -> List[str]:
    if not sentences:
        return []
    chunks: List[str] = []
    current: List[str] = []
    current_tokens = 0
    for sentence in sentences:
        sent_tokens = _estimate_tokens(sentence, lang)
        if current and current_tokens + sent_tokens > target_tokens:
            chunk_text = _join_sentences(current, lang)
            if chunk_text:
                chunks.append(chunk_text)
            if overlap_tokens > 0 and current:
                overlap_acc = 0
                overlap_sentences: List[str] = []
                for s in reversed(current):
                    overlap_acc += _estimate_tokens(s, lang)
                    overlap_sentences.insert(0, s)
                    if overlap_acc >= overlap_tokens:
                        break
                current = overlap_sentences.copy()
                current_tokens = sum(_estimate_tokens(s, lang) for s in current)
            else:
                current = []
                current_tokens = 0
        current.append(sentence)
        current_tokens += sent_tokens

    chunk_text = _join_sentences(current, lang)
    if chunk_text:
        chunks.append(chunk_text)
    return chunks


def _split_code_block(block: str, max_lines: int, overlap_lines: int) -> List[str]:
    normalized = block.strip("\n")
    if not normalized:
        return []
    lines = normalized.splitlines()
    if not lines:
        return []

    fence_line = lines[0].strip()
    fence = "```"
    lang_hint = ""
    if fence_line.startswith("```") or fence_line.startswith("~~~"):
        fence = fence_line[:3]
        lang_hint = fence_line[3:].strip()
        lines = lines[1:]

    if lines and lines[-1].strip().startswith(fence):
        lines = lines[:-1]

    if max_lines <= 0:
        max_lines = len(lines)
    if overlap_lines < 0:
        overlap_lines = 0

    chunks: List[str] = []
    start = 0
    total = len(lines)
    while start < total:
        end = min(total, start + max_lines)
        body = "\n".join(lines[start:end]).rstrip()
        header = f"{fence}{(' ' + lang_hint) if lang_hint else ''}"
        chunk = f"{header}\n{body}\n{fence}"
        chunks.append(chunk.strip("\n"))
        if end >= total:
            break
        if overlap_lines > 0:
            start = max(end - overlap_lines, start + 1)
        else:
            start = end
    return chunks or [normalized]


def _extract_segments(text: str) -> List[tuple[str, str]]:
    segments: List[tuple[str, str]] = []
    if not text:
        return segments
    lines = text.splitlines()
    buffer: List[str] = []
    code_buffer: List[str] = []
    in_code = False
    fence = ""

    for line in lines:
        stripped = line.strip()
        if not in_code and (stripped.startswith("```") or stripped.startswith("~~~")):
            if buffer:
                segments.append(("text", "\n".join(buffer).strip("\n")))
                buffer = []
            in_code = True
            fence = stripped[:3]
            code_buffer = [line]
            continue
        if in_code:
            code_buffer.append(line)
            if stripped.startswith(fence):
                segments.append(("code", "\n".join(code_buffer).strip("\n")))
                in_code = False
                fence = ""
                code_buffer = []
            continue
        buffer.append(line)

    if code_buffer:
        segments.append(("code", "\n".join(code_buffer).strip("\n")))
    if buffer:
        segments.append(("text", "\n".join(buffer).strip("\n")))
    return [segment for segment in segments if segment[1]]


@lru_cache(maxsize=8)
def _get_spacy_nlp_for_lang(lang: str):
    """Load a lightweight spaCy pipeline for sentence splitting (en only)."""
    language = (lang or "").lower().strip() or "en"
    try:
        import spacy  # type: ignore
    except Exception:
        return None

    if language == "en":
        try:
            nlp = spacy.blank("en")
            if "sentencizer" not in nlp.pipe_names:
                nlp.add_pipe("sentencizer")
            return nlp
        except Exception:
            return None

    # For zh/ja and other languages we fall back to regex-based splitting
    if language in {"zh", "ja"}:
        return None

    # Allow advanced users to plug custom models via environment if desired
    path = getattr(settings, "SPACY_MODEL_PATH_EN", None) or os.getenv("SPACY_MODEL_PATH_EN")
    name = getattr(settings, "SPACY_MODEL_EN", None) or "en_core_web_sm"
    try:
        if path and os.path.exists(str(path)):
            return spacy.load(str(path))
        return spacy.load(str(name))
    except Exception:
        return None


async def get_spacy_nlp_for_lang(lang: str):
    """在线程池中加载 spaCy 模型以避免阻塞事件循环。"""
    return await run_in_threadpool(_get_spacy_nlp_for_lang, lang)


def _split_text_sync(
    content: str,
    target: int | None = None,
    overlap: int | None = None,
    doc_language: str | None = None,
    config: DynamicSettingsMapping | None = None,
) -> List[SplitChunk]:
    text = (content or "").strip()
    if not text:
        return []

    primary_lang = (doc_language or _detect_language(text)).lower()
    segments = _extract_segments(text)
    if not segments:
        segments = [("text", text)]

    chunks: List[SplitChunk] = []
    code_max_lines = _coerce_config_value(
        config,
        "RAG_CODE_CHUNK_MAX_LINES",
        settings.RAG_CODE_CHUNK_MAX_LINES,
        int,
    )
    code_overlap_lines = _coerce_config_value(
        config,
        "RAG_CODE_CHUNK_OVERLAP_LINES",
        settings.RAG_CODE_CHUNK_OVERLAP_LINES,
        int,
    )
    overlap_ratio = _coerce_config_value(
        config,
        "RAG_CHUNK_OVERLAP_RATIO",
        settings.RAG_CHUNK_OVERLAP_RATIO,
        float,
    )
    for kind, segment_text in segments:
        if not segment_text or not segment_text.strip():
            continue
        if kind == "code":
            code_chunks = _split_code_block(
                segment_text,
                code_max_lines,
                code_overlap_lines,
            )
            for piece in code_chunks:
                if piece.strip():
                    chunks.append(SplitChunk(content=piece.strip(), language="code", is_code=True))
            continue

        seg_lang = _detect_language(segment_text, primary_lang)
        target_tokens = target or _chunk_target_tokens_for_lang(seg_lang, config)
        overlap_tokens = overlap or max(1, int(target_tokens * overlap_ratio))
        sentences = _segment_sentences(segment_text, seg_lang)
        if not sentences:
            sentences = [segment_text.strip()]
        text_chunks = _pack_sentences(sentences, seg_lang, target_tokens, overlap_tokens)
        for piece in text_chunks:
            if piece.strip():
                chunks.append(SplitChunk(content=piece.strip(), language=seg_lang, is_code=False))

    if not chunks:
        return [SplitChunk(content=text, language=primary_lang, is_code=False)]
    return chunks


async def split_text(
    content: str,
    target: int | None = None,
    overlap: int | None = None,
    doc_language: str | None = None,
    config: DynamicSettingsMapping | None = None,
) -> List[SplitChunk]:
    """在线程池中执行分句逻辑，避免阻塞事件循环。"""
    return await run_in_threadpool(
        _split_text_sync,
        content,
        target,
        overlap,
        doc_language,
        config,
    )


def _strip_markdown_sync(content: str) -> str:
    """将 Markdown 文本转换为纯文本。

    策略：先用 markdown 库转 HTML，再用 BeautifulSoup 提取纯文本；
    移除脚本/样式、图片，并保持代码块为 ``` 包裹文本。
    """
    if not content:
        return ""
    try:
        html = markdown(content, output_format="html")
    except Exception:
        # 回退：若 markdown 渲染失败，直接使用原文
        html = content

    soup = BeautifulSoup(html, "html.parser")

    # 移除无关或噪声节点
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # 处理代码块：保留并显式包裹为 ```lang ... ```
    for pre in soup.find_all("pre"):
        code = pre.find("code")
        code_text = code.get_text("\n") if code else pre.get_text("\n")
        language = ""
        if code and code.has_attr("class"):
            for cls in code["class"]:
                if cls.startswith("language-"):
                    language = cls.replace("language-", "").strip()
                    break
        replacement = soup.new_string(
            f"\n```{language}\n{code_text.strip()}\n```\n"
        )
        pre.replace_with(replacement)

    # 将行内 code 转换为反引号包裹
    for code in soup.find_all("code"):
        if code.parent and code.parent.name == "pre":
            continue
        replacement = soup.new_string(f"`{code.get_text().strip()}`")
        code.replace_with(replacement)

    # 移除图片但保留 alt 文本
    for img in soup.find_all("img"):
        alt_text = img.get("alt") or ""
        img.replace_with(soup.new_string(alt_text))

    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


async def _strip_markdown(content: str) -> str:
    """在线程池中清洗 Markdown 内容，避免阻塞事件循环。"""
    return await run_in_threadpool(_strip_markdown_sync, content)


async def ingest_document_file(
    db: AsyncSession,
    document_id: int,
    upload: UploadFile,
    overwrite: bool = False,
    document: models.KnowledgeDocument | None = None,
    dynamic_settings_service: DynamicSettingsService | None = None,
) -> int:
    """读取上传的纯文本/Markdown 文件并复用文本注入逻辑。"""
    if upload is None:
        raise ValueError("missing_file")

    if not (_allowed_text_mime(upload.content_type) or _allowed_text_suffix(upload.filename)):
        raise ValueError("unsupported_file_type")

    raw = await upload.read()
    # 尝试以常见编码解码为字符串
    content = _decode_bytes_to_text(raw)

    return await ingest_document_content(
        db,
        document_id,
        content,
        overwrite=overwrite,
        document=document,
        dynamic_settings_service=dynamic_settings_service,
    )


async def ingest_document_content(
    db: AsyncSession,
    document_id: int,
    content: str,
    overwrite: bool = False,
    document: models.KnowledgeDocument | None = None,
    dynamic_settings_service: DynamicSettingsService | None = None,
) -> int:
    """将文本切分并写入指定文档的知识块，返回块数量。

    注意：文本清洗、分句与向量编码均在线程池中执行，以避免阻塞事件循环。
    """
    # 新增步骤：在所有操作之前，先清理传入的 content
    plain_text_content = await _strip_markdown(content)

    if document is None:
        document = await crud_knowledge_base.get_document_by_id(db, document_id)

    # 根据覆盖标志，先删除旧分块，避免数据冗余
    # 在线程池中进行分句（使用清理后的纯文本）
    doc_lang = document.language if document and document.language else None
    config = await _resolve_dynamic_settings(dynamic_settings_service)
    split_chunks = await split_text(plain_text_content, doc_language=doc_lang, config=config)
    if not split_chunks:
        # 若选择覆盖且新内容为空，确保删除提交
        if overwrite:
            await crud_knowledge_base.delete_chunks_by_document_id(db, document_id, commit=True)
        return 0
    if overwrite:
        await crud_knowledge_base.delete_chunks_by_document_id(db, document_id, commit=False)
    # 在线程池中进行向量编码
    texts = [chunk.content for chunk in split_chunks]
    vectors = await run_in_threadpool(_model.encode, texts, normalize_embeddings=True)
    payloads = [
        (idx, chunk_info.content, vector, chunk_info.language)
        for idx, (chunk_info, vector) in enumerate(zip(split_chunks, vectors))
    ]

    await crud_knowledge_base.bulk_create_document_chunks(
        db,
        document_id,
        payloads,
        commit=True,
    )

    return len(payloads)


async def update_chunk(
    db: AsyncSession,
    chunk_id: int,
    updates: dict,
) -> models.KnowledgeChunk | None:
    """更新指定知识块内容或排序，并在内容变化时重计算向量。"""
    chunk = await crud_knowledge_base.get_chunk_by_id(db, chunk_id)
    if not chunk:
        return None

    content_changed = False

    if "content" in updates:
        new_content = updates.get("content")
        if new_content is not None and new_content != chunk.content:
            chunk.content = new_content
            content_changed = True
        elif new_content is None and chunk.content is not None:
            # 允许显式清空内容
            chunk.content = ""
            content_changed = True

    if "chunk_index" in updates:
        chunk.chunk_index = updates.get("chunk_index")

    language_changed = False
    if "language" in updates:
        chunk.language = updates.get("language")
        language_changed = True

    needs_persist = content_changed or ("chunk_index" in updates) or language_changed

    if content_changed:
        vector = (
            await run_in_threadpool(_model.encode, [chunk.content], normalize_embeddings=True)
        )[0]
        chunk.embedding = vector
        stripped = chunk.content.strip()
        if stripped.startswith("```"):
            chunk.language = "code"
        else:
            chunk.language = _detect_language(stripped or "")

    if needs_persist:
        await crud_knowledge_base.persist_chunk(db, chunk)

    return chunk


async def delete_chunk(db: AsyncSession, chunk_id: int) -> bool:
    """删除指定知识块。"""
    chunk = await crud_knowledge_base.get_chunk_by_id(db, chunk_id)
    if not chunk:
        return False

    await crud_knowledge_base.delete_chunk(db, chunk)
    return True


async def search_similar_chunks(
    db: AsyncSession,
    query: str,
    top_k: int,
    dynamic_settings_service: DynamicSettingsService | None = None,
    config: DynamicSettingsMapping | None = None,
) -> List[RetrievedChunk]:
    """检索最相似的知识块，带最小相似度阈值、语言偏置与 MMR 去冗。"""

    if top_k <= 0:
        return []

    config_map = config if config is not None else await _resolve_dynamic_settings(dynamic_settings_service)
    oversample_factor = max(
        1,
        _coerce_config_value(config_map, "RAG_OVERSAMPLE", settings.RAG_OVERSAMPLE, int),
    )
    limit_cap = max(
        top_k,
        _coerce_config_value(config_map, "RAG_MAX_CANDIDATES", settings.RAG_MAX_CANDIDATES, int),
    )
    language_bonus = _coerce_config_value(
        config_map, "RAG_SAME_LANG_BONUS", settings.RAG_SAME_LANG_BONUS, float
    )
    min_sim = _coerce_config_value(config_map, "RAG_MIN_SIM", settings.RAG_MIN_SIM, float)
    min_sim = max(0.0, min(1.0, min_sim))
    mmr_lambda = _coerce_config_value(
        config_map, "RAG_MMR_LAMBDA", settings.RAG_MMR_LAMBDA, float
    )
    per_doc_limit = _coerce_config_value(
        config_map, "RAG_PER_DOC_LIMIT", settings.RAG_PER_DOC_LIMIT, int
    )

    q_lang = _detect_language(query)
    q_emb = (await run_in_threadpool(_model.encode, [query], normalize_embeddings=True))[0]

    oversample = max(top_k * oversample_factor, top_k)
    limit = min(limit_cap, oversample)

    candidates: List[RetrievedChunk] = []

    rows = await crud_knowledge_base.fetch_chunk_candidates_by_embedding(db, q_emb, limit)

    for chunk, distance in rows:
        distance_val = float(distance)
        similarity = max(0.0, 1.0 - distance_val)
        score = similarity
        chunk_lang = (chunk.language or "").lower() if getattr(chunk, "language", None) else ""
        if q_lang and chunk_lang and chunk_lang == q_lang:
            score += language_bonus
        embedding_vector = np.array(chunk.embedding, dtype=np.float32)
        candidates.append(
            RetrievedChunk(
                chunk=chunk,
                distance=distance_val,
                similarity=similarity,
                score=score,
                embedding=embedding_vector,
            )
        )

    filtered = [item for item in candidates if item.similarity >= min_sim]
    if not filtered:
        return []

    # 预排序提升 MMR 起点
    filtered.sort(key=lambda item: item.score, reverse=True)

    selected = _mmr_select(filtered, top_k, mmr_lambda, per_doc_limit)

    if not selected:
        return []

    selected.sort(key=lambda item: (item.score, item.similarity), reverse=True)
    return selected
