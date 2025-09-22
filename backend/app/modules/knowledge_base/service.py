from __future__ import annotations

from typing import Any, Callable, Iterable, List, Mapping, Optional, TypeVar
from dataclasses import dataclass
import math
import logging
import threading
import time
from collections import defaultdict

import numpy as np

from sentence_transformers import SentenceTransformer, CrossEncoder
from fastapi.concurrency import run_in_threadpool
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infrastructure.dynamic_settings import DynamicSettingsService
from . import models
from .repository import crud_knowledge_base
from .ingest_extractor import ExtractedElement, extract_from_bytes, extract_from_text
from .ingest_language import detect_language, lingua_status
from .ingest_splitter import SplitChunk, split_elements


# 嵌入模型（CPU 上加载，保持与 DB 维度一致）
_model = SentenceTransformer(settings.EMBEDDING_MODEL)
_reranker_lock = threading.Lock()
_reranker_instance: CrossEncoder | None = None
@dataclass(slots=True)
class RetrievedChunk:
    chunk: "models.KnowledgeChunk"
    distance: float
    similarity: float
    score: float
    embedding: np.ndarray
    language_bonus: float = 0.0
    coarse_score: float = 0.0
    mmr_score: float = 0.0
    rerank_score: float | None = None


logger = logging.getLogger(__name__)

T = TypeVar("T")
DynamicSettingsMapping = Mapping[str, Any]


def _coerce_bool(
    config: DynamicSettingsMapping | None,
    key: str,
    default: bool,
) -> bool:
    source = default if config is None else config.get(key, default)
    if isinstance(source, str):
        return source.strip().lower() in {"1", "true", "yes", "on"}
    return bool(source)


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


def _batched(items: Iterable[Any], size: int) -> Iterable[list[Any]]:
    batch: list[Any] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


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


def _detect_language(text: str, config: DynamicSettingsMapping | None) -> str:
    return detect_language(text, config)


def _sigmoid(value: float) -> float:
    try:
        if value >= 0:
            z = math.exp(-value)
            return 1.0 / (1.0 + z)
        z = math.exp(value)
        return z / (1.0 + z)
    except OverflowError:
        return 0.0 if value < 0 else 1.0


def _get_reranker() -> CrossEncoder:
    global _reranker_instance
    if _reranker_instance is not None:
        return _reranker_instance

    with _reranker_lock:
        if _reranker_instance is None:
            model_name = settings.RERANKER_MODEL
            if not model_name:
                raise RuntimeError("RERANKER_MODEL is not configured")
            logger.info("Loading reranker model %s", model_name)
            _reranker_instance = CrossEncoder(model_name)
    return _reranker_instance


def _build_rerank_preview(content: str, limit: int = 512) -> str:
    """Trim content for reranker input while trying to respect sentence boundaries."""

    text = (content or "").strip()
    if len(text) <= limit:
        return text

    cutoff = -1
    boundary_markers = ["\n", "。", "！", "!", "?", "？", "."]
    for marker in boundary_markers:
        idx = text.rfind(marker, 0, limit)
        if idx > cutoff:
            cutoff = idx

    if cutoff >= int(limit * 0.6):
        return text[: cutoff + 1].strip()

    return text[:limit].rstrip()


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


def _ensure_elements(
    elements: list[ExtractedElement],
    fallback_text: str | None,
    source_ref: str | None,
) -> list[ExtractedElement]:
    if elements:
        return elements
    text = (fallback_text or "").strip()
    if not text:
        return []
    metadata = {"source": source_ref} if source_ref else {}
    return [ExtractedElement(text=text, metadata=metadata)]


async def _split_elements_async(
    elements: list[ExtractedElement],
    config: DynamicSettingsMapping | None,
) -> List[SplitChunk]:
    if not elements:
        return []
    return await run_in_threadpool(split_elements, elements, config=config)


async def _persist_chunks(
    db: AsyncSession,
    *,
    document_id: int,
    elements: list[ExtractedElement],
    overwrite: bool,
    dynamic_settings_service: DynamicSettingsService | None,
) -> int:
    config = await _resolve_dynamic_settings(dynamic_settings_service)
    split_chunks = await _split_elements_async(elements, config)
    if not split_chunks:
        if overwrite:
            await crud_knowledge_base.delete_chunks_by_document_id(db, document_id, commit=True)
        return 0

    if overwrite:
        await crud_knowledge_base.delete_chunks_by_document_id(db, document_id, commit=False)

    texts = [chunk.content for chunk in split_chunks]
    vectors = await run_in_threadpool(_model.encode, texts, normalize_embeddings=True)
    payloads = [
        (idx, chunk.content, vector, chunk.language)
        for idx, (chunk, vector) in enumerate(zip(split_chunks, vectors))
    ]

    await crud_knowledge_base.bulk_create_document_chunks(
        db,
        document_id,
        payloads,
        commit=True,
    )

    return len(payloads)


async def ingest_document_file(
    db: AsyncSession,
    document_id: int,
    upload: UploadFile,
    overwrite: bool = False,
    document: models.KnowledgeDocument | None = None,
    dynamic_settings_service: DynamicSettingsService | None = None,
) -> int:
    """Ingest an uploaded document by extracting, chunking, and storing its elements."""

    if upload is None:
        raise ValueError("missing_file")

    raw = await upload.read()
    if document is None:
        document = await crud_knowledge_base.get_document_by_id(db, document_id)

    filename = upload.filename or (document.source_ref if document else None)
    content_type = upload.content_type

    fallback_text, elements = await run_in_threadpool(
        extract_from_bytes,
        raw,
        filename=filename,
        content_type=content_type,
    )

    normalized_elements = _ensure_elements(elements, fallback_text, filename)

    return await _persist_chunks(
        db,
        document_id=document_id,
        elements=normalized_elements,
        overwrite=overwrite,
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
    """Ingest raw text content provided directly via API."""

    if document is None:
        document = await crud_knowledge_base.get_document_by_id(db, document_id)

    source_ref = document.source_ref if document and document.source_ref else None
    elements = await run_in_threadpool(extract_from_text, content or "", source_ref=source_ref)
    normalized_elements = _ensure_elements(elements, content, source_ref)

    return await _persist_chunks(
        db,
        document_id=document_id,
        elements=normalized_elements,
        overwrite=overwrite,
        dynamic_settings_service=dynamic_settings_service,
    )


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
        stripped = (chunk.content or "").strip()
        chunk.language = detect_language(stripped or "")

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
    rerank_enabled = _coerce_bool(
        config_map, "RAG_RERANK_ENABLED", settings.RAG_RERANK_ENABLED
    )
    rerank_candidates = max(
        top_k,
        _coerce_config_value(
            config_map, "RAG_RERANK_CANDIDATES", settings.RAG_RERANK_CANDIDATES, int
        ),
    )
    rerank_score_threshold = _coerce_config_value(
        config_map,
        "RAG_RERANK_SCORE_THRESHOLD",
        settings.RAG_RERANK_SCORE_THRESHOLD,
        float,
    )
    rerank_score_threshold = max(0.0, min(1.0, rerank_score_threshold))
    rerank_max_batch = max(
        1,
        _coerce_config_value(
            config_map, "RAG_RERANK_MAX_BATCH", settings.RAG_RERANK_MAX_BATCH, int
        ),
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
    
    logger.debug("rag_lang_status %s", lingua_status(config_map))
    q_lang = _detect_language(query, config_map)
    q_emb = (await run_in_threadpool(_model.encode, [query], normalize_embeddings=True))[0]

    oversample = max(top_k * oversample_factor, top_k)
    if rerank_enabled:
        oversample = max(oversample, rerank_candidates)
    limit = min(limit_cap, oversample)

    logger.info(
        "rag_search_params top_k=%s oversample_factor=%s limit_cap=%s effective_limit=%s min_sim=%.4f mmr_lambda=%.4f per_doc_limit=%s rerank_enabled=%s rerank_candidates=%s rerank_threshold=%.4f",
        top_k,
        oversample_factor,
        limit_cap,
        limit,
        min_sim,
        mmr_lambda,
        per_doc_limit,
        rerank_enabled,
        rerank_candidates,
        rerank_score_threshold,
    )

    candidates: List[RetrievedChunk] = []

    rows = await crud_knowledge_base.fetch_chunk_candidates_by_embedding(db, q_emb, limit)

    for chunk, distance in rows:
        distance_val = float(distance)
        similarity = max(0.0, 1.0 - distance_val)
        score = similarity
        language_bonus_value = 0.0
        chunk_lang = (chunk.language or "").lower() if getattr(chunk, "language", None) else ""
        if q_lang and chunk_lang and chunk_lang == q_lang:
            language_bonus_value = language_bonus
            score += language_bonus_value
        embedding_vector = np.array(chunk.embedding, dtype=np.float32)
        candidates.append(
            RetrievedChunk(
                chunk=chunk,
                distance=distance_val,
                similarity=similarity,
                score=score,
                embedding=embedding_vector,
                language_bonus=language_bonus_value,
                coarse_score=score,
            )
        )

    filtered = [item for item in candidates if item.similarity >= min_sim]
    if not filtered:
        return []

    filtered.sort(key=lambda item: item.score, reverse=True)

    rerank_stats: dict[str, Any] = {}

    if rerank_enabled and filtered:
        start_time = time.perf_counter()
        rerank_limit = min(len(filtered), rerank_candidates)
        head = filtered[:rerank_limit]
        tail = filtered[rerank_limit:]
        rerank_stats = {
            "rerank_candidates": len(head),
            "rerank_threshold": rerank_score_threshold,
        }

        rerank_scores: list[float] = []
        try:
            reranker = _get_reranker()
            pairs = []
            for item in head:
                content = getattr(item.chunk, "content", "") or ""
                preview = _build_rerank_preview(content)
                pairs.append([query, preview])

            for batch_pairs in _batched(pairs, rerank_max_batch):
                raw_scores = await run_in_threadpool(
                    reranker.predict,
                    batch_pairs,
                    convert_to_numpy=True,
                    batch_size=min(rerank_max_batch, len(batch_pairs)),
                    show_progress_bar=False,
                )
                for raw in raw_scores:
                    rerank_scores.append(float(raw))
        except Exception as exc:  # pragma: no cover - safety fallback
            logger.warning(
                "Cross-encoder rerank failed: %s", exc, exc_info=logger.isEnabledFor(logging.DEBUG)
            )
            rerank_scores.clear()

        rerank_stats["rerank_duration_ms"] = round(
            (time.perf_counter() - start_time) * 1000, 3
        )

        if rerank_scores:
            probabilities = [_sigmoid(score) for score in rerank_scores]
            above_threshold = sum(prob >= rerank_score_threshold for prob in probabilities)
            for item, prob in zip(head, probabilities):
                item.rerank_score = prob
                coarse_without_bonus = max(0.0, item.coarse_score - item.language_bonus)
                adjusted = prob
                if prob < rerank_score_threshold:
                    adjusted = (prob + coarse_without_bonus) / 2.0
                item.score = adjusted + item.language_bonus

            for leftover in head[len(probabilities) :]:
                leftover.score = leftover.coarse_score
                leftover.rerank_score = None

            rerank_stats.update(
                {
                    "rerank_above_threshold": above_threshold,
                    "rerank_below_threshold": len(probabilities) - above_threshold,
                    "rerank_avg_score": float(
                        sum(probabilities) / len(probabilities)
                    ),
                }
            )
        else:
            for item in head:
                item.score = item.coarse_score
                item.rerank_score = None

        filtered = head + tail
        filtered.sort(key=lambda item: item.score, reverse=True)

    selected = _mmr_select(filtered, top_k, mmr_lambda, per_doc_limit)

    if not selected:
        return []

    selected.sort(key=lambda item: (item.mmr_score, item.score, item.similarity), reverse=True)

    logger.debug(
        "rag_retrieval",
        extra={
            "requested_top_k": top_k,
            "retrieved_candidates": len(candidates),
            "filtered_after_min_sim": len(filtered),
            "selected_count": len(selected),
            "rerank_enabled": rerank_enabled,
            **rerank_stats,
        },
    )
    return selected
