from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List

import numpy as np
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from . import models
from .bm25 import fetch_bm25_matches
from .config import DynamicSettingsMapping, RagSearchConfig, build_rag_config
from .embeddings import get_embedder
from .language import detect_language
from .repository import crud_knowledge_base

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RetrievedChunk:
    """Lightweight container returned to the chat layer."""

    chunk: "models.KnowledgeChunk"
    score: float
    similarity: float
    retrieval_source: str
    vector_score: float = 0.0
    bm25_score: float = 0.0


def _language_bonus(query_lang: str, chunk_lang: str) -> float:
    if not query_lang or not chunk_lang:
        return 0.0
    return 0.05 if query_lang == chunk_lang else 0.0


def _effective_top_k(config: RagSearchConfig) -> int:
    return max(1, config.top_k)


async def _vector_candidates(
    db: AsyncSession,
    query_embedding: np.ndarray,
    top_k: int,
    query_lang: str,
) -> Dict[int, RetrievedChunk]:
    rows = await crud_knowledge_base.fetch_chunk_candidates_by_embedding(
        db,
        query_embedding,
        top_k * 2,
    )
    items: Dict[int, RetrievedChunk] = {}
    for chunk, distance in rows:
        distance_val = float(distance)
        similarity = max(0.0, 1.0 - distance_val)
        chunk_lang = (chunk.language or "").lower() if getattr(chunk, "language", None) else ""
        bonus = _language_bonus(query_lang, chunk_lang)
        score = similarity + bonus
        items[chunk.id] = RetrievedChunk(
            chunk=chunk,
            score=score,
            similarity=similarity,
            retrieval_source="vector",
            vector_score=similarity,
            bm25_score=0.0,
        )
    return items


async def _bm25_candidates(
    db: AsyncSession,
    query: str,
    top_k: int,
    config: DynamicSettingsMapping,
) -> Dict[int, tuple["models.KnowledgeChunk", float, float]]:
    if not query.strip():
        return {}

    bm25_config = build_bm25_config(config, requested_top_k=top_k)

    search_result = await fetch_bm25_matches(
        db,
        query,
        bm25_config.search_limit,
        min_rank=bm25_config.min_rank,
        language="",
    )

    scores: Dict[int, tuple["models.KnowledgeChunk", float, float]] = {}
    for match in search_result.matches:
        scores[match.chunk.id] = (match.chunk, match.normalized_score, match.raw_score)
    return scores


def _merge_candidates(
    vector_hits: Dict[int, RetrievedChunk],
    bm25_hits: Dict[int, tuple["models.KnowledgeChunk", float, float]],
    query_lang: str,
) -> List[RetrievedChunk]:
    merged: Dict[int, RetrievedChunk] = dict(vector_hits)

    for chunk_id, (chunk, normalized, raw_score) in bm25_hits.items():
        if chunk_id in merged:
            item = merged[chunk_id]
            item.bm25_score = raw_score
            item.retrieval_source = "hybrid"
            candidate = max(item.vector_score, normalized)
            chunk_lang = (item.chunk.language or "").lower() if getattr(item.chunk, "language", None) else ""
            item.score = candidate + _language_bonus(query_lang, chunk_lang)
            item.similarity = max(item.similarity, normalized)
        else:
            chunk_lang = (chunk.language or "").lower() if getattr(chunk, "language", None) else ""
            bonus = _language_bonus(query_lang, chunk_lang)
            merged[chunk_id] = RetrievedChunk(
                chunk=chunk,
                score=normalized + bonus,
                similarity=normalized,
                retrieval_source="bm25",
                vector_score=0.0,
                bm25_score=raw_score,
            )

    return list(merged.values())


async def search_similar_chunks(
    db: AsyncSession,
    query: str,
    top_k: int,
    config: DynamicSettingsMapping,
) -> List[RetrievedChunk]:
    """Fetch a generous batch of candidates via vector + BM25 and let Gemini digest them."""
    if top_k <= 0 or not query.strip():
        return []

    rag_config = build_rag_config(config, requested_top_k=top_k)
    effective_top_k = _effective_top_k(rag_config)

    embedder = get_embedder()
    query_embedding = (
        await run_in_threadpool(embedder.encode, [query], normalize_embeddings=True)
    )[0]

    query_lang = detect_language(query)
    vector_hits = await _vector_candidates(
        db,
        query_embedding,
        effective_top_k,
        query_lang,
    )
    bm25_hits = await _bm25_candidates(db, query, effective_top_k, config)

    merged = _merge_candidates(vector_hits, bm25_hits, query_lang)

    merged.sort(key=lambda item: item.score, reverse=True)
    trimmed = merged[:effective_top_k]

    logger.debug(
        "retrieval simplified: query_lang=%s vector=%s bm25=%s delivered=%s",
        query_lang,
        len(vector_hits),
        len(bm25_hits),
        len(trimmed),
    )
    return trimmed


__all__ = ["RetrievedChunk", "search_similar_chunks"]
