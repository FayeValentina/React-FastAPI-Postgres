from __future__ import annotations

from typing import Any, Iterable, List, Mapping, Optional
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
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infrastructure.dynamic_settings import DynamicSettingsService
from . import models
from .repository import crud_knowledge_base
from .bm25 import fetch_bm25_matches, to_numpy_embedding
from .ingest_extractor import ExtractedElement, extract_from_bytes, extract_from_text
from .ingest_language import detect_language, detect_language_meta, lingua_status
from .ingest_splitter import SplitChunk, split_elements
from .tokenizer import tokenize_for_search
from .utils import coerce_bool, coerce_value


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
    bm25_score: float | None = None
    retrieval_source: str = "vector"
    vector_score: float = 0.0


logger = logging.getLogger(__name__)

DynamicSettingsMapping = Mapping[str, Any]


@dataclass(slots=True)
class RagSearchConfig:
    effective_top_k: int
    oversample_factor: int
    limit_cap: int
    rerank_enabled: bool
    rerank_candidates: int
    rerank_score_threshold: float
    rerank_max_batch: int
    language_bonus: float
    min_sim: float
    mmr_lambda: float
    per_doc_limit: int
    bm25_enabled: bool
    bm25_top_k: int
    bm25_weight: float
    bm25_min_score: float


def _build_rag_config(
    config_map: DynamicSettingsMapping | None,
    *,
    requested_top_k: int,
) -> RagSearchConfig:
    base_top_k = max(1, requested_top_k)
    config_top_k = coerce_value(config_map, "RAG_TOP_K", settings.RAG_TOP_K, int)
    effective_top_k = max(base_top_k, config_top_k)
    oversample_factor = max(
        1,
        coerce_value(config_map, "RAG_OVERSAMPLE", settings.RAG_OVERSAMPLE, int),
    )
    limit_cap = max(
        effective_top_k,
        coerce_value(config_map, "RAG_MAX_CANDIDATES", settings.RAG_MAX_CANDIDATES, int),
    )
    rerank_enabled = coerce_bool(
        config_map, "RAG_RERANK_ENABLED", settings.RAG_RERANK_ENABLED
    )
    rerank_candidates = max(
        effective_top_k,
        coerce_value(
            config_map, "RAG_RERANK_CANDIDATES", settings.RAG_RERANK_CANDIDATES, int
        ),
    )
    rerank_score_threshold = coerce_value(
        config_map,
        "RAG_RERANK_SCORE_THRESHOLD",
        settings.RAG_RERANK_SCORE_THRESHOLD,
        float,
    )
    rerank_score_threshold = max(0.0, min(1.0, rerank_score_threshold))
    rerank_max_batch = max(
        1,
        coerce_value(
            config_map, "RAG_RERANK_MAX_BATCH", settings.RAG_RERANK_MAX_BATCH, int
        ),
    )
    language_bonus = coerce_value(
        config_map, "RAG_SAME_LANG_BONUS", settings.RAG_SAME_LANG_BONUS, float
    )
    min_sim = coerce_value(config_map, "RAG_MIN_SIM", settings.RAG_MIN_SIM, float)
    min_sim = max(0.0, min(1.0, min_sim))
    mmr_lambda = coerce_value(
        config_map, "RAG_MMR_LAMBDA", settings.RAG_MMR_LAMBDA, float
    )
    per_doc_limit = coerce_value(
        config_map, "RAG_PER_DOC_LIMIT", settings.RAG_PER_DOC_LIMIT, int
    )

    bm25_enabled_value = coerce_bool(config_map, "BM25_ENABLED", settings.BM25_ENABLED)
    bm25_top_k_value = coerce_value(config_map, "BM25_TOP_K", settings.BM25_TOP_K, int)
    bm25_top_k_value = max(0, bm25_top_k_value)
    bm25_weight_value = coerce_value(config_map, "BM25_WEIGHT", settings.BM25_WEIGHT, float)
    bm25_weight_value = max(0.0, min(1.0, float(bm25_weight_value)))
    bm25_min_score_value = coerce_value(
        config_map, "BM25_MIN_SCORE", settings.BM25_MIN_SCORE, float
    )
    bm25_min_score_value = max(0.0, float(bm25_min_score_value))

    return RagSearchConfig(
        effective_top_k=effective_top_k,
        oversample_factor=oversample_factor,
        limit_cap=limit_cap,
        rerank_enabled=rerank_enabled,
        rerank_candidates=rerank_candidates,
        rerank_score_threshold=rerank_score_threshold,
        rerank_max_batch=rerank_max_batch,
        language_bonus=language_bonus,
        min_sim=min_sim,
        mmr_lambda=mmr_lambda,
        per_doc_limit=per_doc_limit,
        bm25_enabled=bm25_enabled_value,
        bm25_top_k=bm25_top_k_value,
        bm25_weight=bm25_weight_value,
        bm25_min_score=bm25_min_score_value,
    )


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


async def _apply_bm25_fusion(
    db: AsyncSession,
    query: str,
    *,
    q_lang: str,
    q_emb: np.ndarray,
    rag_config: RagSearchConfig,
    candidate_map: dict[int, RetrievedChunk],
    vector_candidates: int,
) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "bm25_enabled": rag_config.bm25_enabled,
        "bm25_weight": round(float(rag_config.bm25_weight), 4),
        "vector_candidates": vector_candidates,
    }

    normalized_scores: dict[int, float] = {}

    if not (rag_config.bm25_enabled and rag_config.bm25_top_k > 0 and query.strip()):
        return stats

    search_result = await fetch_bm25_matches(
        db,
        query,
        rag_config.bm25_top_k,
        min_score=rag_config.bm25_min_score,
        language=q_lang,
        filters={},
    )
    stats["bm25_raw_hits"] = search_result.raw_hits
    stats["bm25_after_threshold"] = search_result.after_threshold

    if not search_result.matches:
        return stats

    if search_result.max_score is not None:
        stats["bm25_max_score"] = float(search_result.max_score)
    if search_result.min_score is not None:
        stats["bm25_min_score"] = float(search_result.min_score)

    for match in search_result.matches:
        chunk = match.chunk
        raw_score = match.raw_score
        normalized = match.normalized_score
        normalized_scores[chunk.id] = normalized

        embedding_vector = to_numpy_embedding(chunk)
        chunk_lang = (chunk.language or "").lower() if getattr(chunk, "language", None) else ""
        language_bonus_value = (
            rag_config.language_bonus
            if q_lang and chunk_lang and chunk_lang == q_lang
            else 0.0
        )
        similarity_estimate = max(0.0, float(np.dot(q_emb, embedding_vector)))
        distance_estimate = max(0.0, 1.0 - similarity_estimate)
        combined_base = (1.0 - rag_config.bm25_weight) * similarity_estimate + rag_config.bm25_weight * normalized
        combined_base = max(0.0, min(1.0, combined_base))

        existing = candidate_map.get(chunk.id)
        if existing is None:
            coarse_score = combined_base + language_bonus_value
            candidate_map[chunk.id] = RetrievedChunk(
                chunk=chunk,
                distance=distance_estimate,
                similarity=similarity_estimate,
                score=coarse_score,
                embedding=embedding_vector,
                language_bonus=language_bonus_value,
                coarse_score=coarse_score,
                bm25_score=raw_score,
                retrieval_source="bm25",
                vector_score=similarity_estimate,
            )
        else:
            existing.bm25_score = raw_score
            if rag_config.bm25_weight > 0:
                existing.retrieval_source = "hybrid"
            existing.vector_score = max(
                float(existing.vector_score), similarity_estimate
            )
            existing.similarity = max(
                float(existing.similarity), similarity_estimate
            )
            base_component = (1.0 - rag_config.bm25_weight) * float(
                existing.vector_score
            ) + rag_config.bm25_weight * normalized
            base_component = max(0.0, min(1.0, base_component))
            existing.coarse_score = base_component + existing.language_bonus
            existing.score = existing.coarse_score

    stats["bm25_fused"] = len(normalized_scores)

    if rag_config.bm25_enabled and rag_config.bm25_weight > 0 and candidate_map:
        for item in candidate_map.values():
            normalized = normalized_scores.get(item.chunk.id, 0.0)
            base_component = (1.0 - rag_config.bm25_weight) * float(item.vector_score) + rag_config.bm25_weight * normalized
            base_component = max(0.0, min(1.0, base_component))
            item.coarse_score = base_component + item.language_bonus
            item.score = item.coarse_score
            if normalized > 0.0 and item.retrieval_source == "vector":
                item.retrieval_source = "hybrid"

    return stats


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

    _, elements = await run_in_threadpool(
        extract_from_bytes,
        raw,
        filename=filename,
        content_type=content_type,
    )

    return await _persist_chunks(
        db,
        document_id=document_id,
        elements=elements,
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

    return await _persist_chunks(
        db,
        document_id=document_id,
        elements=elements,
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
        meta = detect_language_meta(stripped or "")
        chunk.language = meta["language"]

    if content_changed or language_changed:
        search_text = tokenize_for_search(chunk.content, chunk.language)
        chunk.search_vector = func.to_tsvector("simple", search_text)

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
    rag_config = _build_rag_config(
        config_map,
        requested_top_k=top_k,
    )

    logger.debug("rag_lang_status %s", lingua_status(config_map))
    q_lang = _detect_language(query, config_map)
    q_emb = (await run_in_threadpool(_model.encode, [query], normalize_embeddings=True))[0]

    oversample = max(top_k * rag_config.oversample_factor, top_k)
    if rag_config.rerank_enabled:
        oversample = max(oversample, rag_config.rerank_candidates)
    limit = min(rag_config.limit_cap, oversample)

    logger.info(
        (
            "rag_search_params top_k=%s oversample_factor=%s limit_cap=%s effective_limit=%s "
            "min_sim=%.4f mmr_lambda=%.4f per_doc_limit=%s rerank_enabled=%s rerank_candidates=%s "
            "rerank_threshold=%.4f bm25_enabled=%s bm25_top_k=%s bm25_weight=%.3f bm25_min_score=%.3f"
        ),
        top_k,
        rag_config.oversample_factor,
        rag_config.limit_cap,
        limit,
        rag_config.min_sim,
        rag_config.mmr_lambda,
        rag_config.per_doc_limit,
        rag_config.rerank_enabled,
        rag_config.rerank_candidates,
        rag_config.rerank_score_threshold,
        rag_config.bm25_enabled,
        rag_config.bm25_top_k,
        rag_config.bm25_weight,
        rag_config.bm25_min_score,
    )

    candidates: List[RetrievedChunk] = []

    rows = await crud_knowledge_base.fetch_chunk_candidates_by_embedding(db, q_emb, limit)

    for chunk, distance in rows:
        distance_val = float(distance)
        similarity = max(0.0, 1.0 - distance_val)
        base_score = similarity
        language_bonus_value = 0.0
        chunk_lang = (chunk.language or "").lower() if getattr(chunk, "language", None) else ""
        if q_lang and chunk_lang and chunk_lang == q_lang:
            language_bonus_value = rag_config.language_bonus
            base_score += language_bonus_value
        embedding_vector = np.array(chunk.embedding, dtype=np.float32)
        candidates.append(
            RetrievedChunk(
                chunk=chunk,
                distance=distance_val,
                similarity=similarity,
                score=base_score,
                embedding=embedding_vector,
                language_bonus=language_bonus_value,
                coarse_score=base_score,
                retrieval_source="vector",
                vector_score=similarity,
            )
        )

    filtered = [item for item in candidates if item.similarity >= rag_config.min_sim]
    candidate_map: dict[int, RetrievedChunk] = {item.chunk.id: item for item in filtered}
    vector_candidates_count = len(filtered)

    bm25_stats = await _apply_bm25_fusion(
        db,
        query,
        q_lang=q_lang,
        q_emb=q_emb,
        rag_config=rag_config,
        candidate_map=candidate_map,
        vector_candidates=vector_candidates_count,
    )

    filtered = list(candidate_map.values())
    filtered.sort(key=lambda item: item.score, reverse=True)

    if not filtered:
        return []

    rerank_stats: dict[str, Any] = {}

    if rag_config.rerank_enabled and filtered:
        start_time = time.perf_counter()
        rerank_limit = min(len(filtered), rag_config.rerank_candidates)
        head = filtered[:rerank_limit]
        tail = filtered[rerank_limit:]
        rerank_stats = {
            "rerank_candidates": len(head),
            "rerank_threshold": rag_config.rerank_score_threshold,
        }

        rerank_scores: list[float] = []
        try:
            reranker = _get_reranker()
            pairs = []
            for item in head:
                content = getattr(item.chunk, "content", "") or ""
                preview = _build_rerank_preview(content)
                pairs.append([query, preview])

            for batch_pairs in _batched(pairs, rag_config.rerank_max_batch):
                batch_size = min(rag_config.rerank_max_batch, len(batch_pairs))
                raw_scores = await run_in_threadpool(
                    reranker.predict,
                    batch_pairs,
                    convert_to_numpy=True,
                    batch_size=batch_size,
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
            above_threshold = sum(
                prob >= rag_config.rerank_score_threshold for prob in probabilities
            )
            for item, prob in zip(head, probabilities):
                item.rerank_score = prob
                coarse_without_bonus = max(0.0, item.coarse_score - item.language_bonus)
                adjusted = prob
                if prob < rag_config.rerank_score_threshold:
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

    selected = _mmr_select(filtered, top_k, rag_config.mmr_lambda, rag_config.per_doc_limit)

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
            "rerank_enabled": rag_config.rerank_enabled,
            **bm25_stats,
            **rerank_stats,
        },
    )
    return selected
