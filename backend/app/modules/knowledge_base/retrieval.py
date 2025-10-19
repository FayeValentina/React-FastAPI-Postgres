from __future__ import annotations

import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, List, Mapping

import numpy as np
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.dynamic_settings import DynamicSettingsService

from . import models
from .bm25 import fetch_bm25_matches, to_numpy_embedding
from .config import (
    DynamicSettingsMapping,
    RagSearchConfig,
    build_rag_config,
    resolve_dynamic_settings,
)
from .embeddings import get_embedder, get_reranker
from .language import detect_language, lingua_status
from .repository import crud_knowledge_base

logger = logging.getLogger(__name__)

LANGUAGE_MATCH_BONUS = 0.12
RERANK_MAX_BATCH = 16


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


def _sigmoid(value: float) -> float:
    try:
        if value >= 0:
            z = math.exp(-value)
            return 1.0 / (1.0 + z)
        z = math.exp(value)
        return z / (1.0 + z)
    except OverflowError:
        return 0.0 if value < 0 else 1.0


def _batched(items: Iterable[Any], size: int) -> Iterable[list[Any]]:
    batch: list[Any] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


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
        "bm25_weight": round(float(rag_config.bm25_weight), 4),
        "vector_candidates": vector_candidates,
    }

    normalized_scores: dict[int, float] = {}

    if not (rag_config.bm25_top_k > 0 and query.strip()):
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
        language_bonus_value = LANGUAGE_MATCH_BONUS if q_lang and chunk_lang and chunk_lang == q_lang else 0.0
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

    if rag_config.bm25_weight > 0 and candidate_map:
        for item in candidate_map.values():
            normalized = normalized_scores.get(item.chunk.id, 0.0)
            base_component = (1.0 - rag_config.bm25_weight) * float(item.vector_score) + rag_config.bm25_weight * normalized
            base_component = max(0.0, min(1.0, base_component))
            item.coarse_score = base_component + item.language_bonus
            item.score = item.coarse_score
            if normalized > 0.0 and item.retrieval_source == "vector":
                item.retrieval_source = "hybrid"

    return stats


async def search_similar_chunks(
    db: AsyncSession,
    query: str,
    top_k: int,
    dynamic_settings_service: DynamicSettingsService | None = None,
    config: DynamicSettingsMapping | None = None,
) -> List[RetrievedChunk]:
    """Retrieve top matching chunks by combining vector search, BM25, reranking, and MMR."""
    if top_k <= 0:
        return []

    config_map = config if config is not None else await resolve_dynamic_settings(dynamic_settings_service)
    rag_config = build_rag_config(config_map, requested_top_k=top_k)

    logger.debug("rag_lang_status %s", lingua_status(config_map))
    query_language = detect_language(query, config_map)
    embedder = get_embedder()
    query_embedding = (await run_in_threadpool(embedder.encode, [query], normalize_embeddings=True))[0]

    oversample = max(top_k * rag_config.oversample_factor, top_k)
    if rag_config.rerank_enabled:
        oversample = max(oversample, rag_config.rerank_candidates)
    limit = min(rag_config.limit_cap, oversample)

    logger.info(
        (
            "rag_search_params top_k=%s oversample_factor=%s limit_cap=%s effective_limit=%s "
            "min_sim=%.4f mmr_lambda=%.4f per_doc_limit=%s rerank_enabled=%s rerank_candidates=%s "
            "rerank_threshold=%.4f bm25_top_k=%s bm25_weight=%.3f bm25_min_score=%.3f"
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
        rag_config.bm25_top_k,
        rag_config.bm25_weight,
        rag_config.bm25_min_score,
    )

    rows = await crud_knowledge_base.fetch_chunk_candidates_by_embedding(db, query_embedding, limit)

    candidates: List[RetrievedChunk] = []
    for chunk, distance in rows:
        distance_val = float(distance)
        similarity = max(0.0, 1.0 - distance_val)
        base_score = similarity
        language_bonus_value = 0.0
        chunk_lang = (chunk.language or "").lower() if getattr(chunk, "language", None) else ""
        if query_language and chunk_lang and chunk_lang == query_language:
            language_bonus_value = LANGUAGE_MATCH_BONUS
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
        q_lang=query_language,
        q_emb=query_embedding,
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
            reranker = get_reranker()
            pairs = []
            for item in head:
                content = getattr(item.chunk, "content", "") or ""
                preview = _build_rerank_preview(content)
                pairs.append([query, preview])

            for batch_pairs in _batched(pairs, RERANK_MAX_BATCH):
                batch_size = min(RERANK_MAX_BATCH, len(batch_pairs))
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


__all__ = ["RetrievedChunk", "search_similar_chunks"]
