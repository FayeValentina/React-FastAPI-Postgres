from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List

import asyncio
import numpy as np
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infrastructure.dynamic_settings import get_dynamic_settings_service

from . import models
from .config import build_bm25_config, build_rag_config
from .embeddings import get_embedder
from .language import detect_language
from .repository import crud_knowledge_base

logger = logging.getLogger(__name__)


async def _load_dynamic_settings():
    """Load dynamic settings with a defensive fallback."""
    service = get_dynamic_settings_service()
    try:
        return await service.get_all()
    except Exception as exc:
        if isinstance(exc, asyncio.CancelledError):
            raise
        logger.exception("Falling back to default dynamic settings during retrieval")
        return settings.dynamic_settings_defaults()


@dataclass(slots=True)
class BM25Match:
    """BM25 匹配结果的数据类"""

    chunk: models.KnowledgeChunk
    raw_score: float
    normalized_score: float


@dataclass(slots=True)
class BM25SearchResult:
    """BM25 搜索结果的数据类"""

    matches: list[BM25Match]
    raw_hits: int
    after_threshold: int


@dataclass(slots=True)
class RetrievedChunk:
    """Lightweight container returned to the chat layer.
    返回给聊天层的轻量级容器。
    """

    chunk: "models.KnowledgeChunk"  # 知识块对象
    score: float  # 最终得分
    similarity: float  # 相似度得分
    retrieval_source: str  # 检索来源 (vector, bm25, hybrid)
    vector_score: float = 0.0  # 向量检索得分
    bm25_score: float = 0.0  # BM25 检索得分


def _normalize_bm25_rows(
    rows: list[tuple["models.KnowledgeChunk", float]],
) -> BM25SearchResult:
    """将数据库返回的 BM25 结果归一化为 0-1 区间。"""
    if not rows:
        return BM25SearchResult(matches=[], raw_hits=0, after_threshold=0)

    raw_scores = [float(score or 0.0) for _, score in rows]
    max_score = max(raw_scores)
    min_score_value = min(raw_scores)
    denom = max(max_score - min_score_value, 1e-6)

    matches: list[BM25Match] = []
    for chunk, score in rows:
        normalized = 1.0 if denom <= 1e-6 else max(
            0.0, min(1.0, (score - min_score_value) / denom)
        )
        matches.append(
            BM25Match(
                chunk=chunk,
                raw_score=score,
                normalized_score=normalized,
            )
        )

    return BM25SearchResult(
        matches=matches,
        raw_hits=len(rows),
        after_threshold=len(rows),
    )

async def vector_search(
    db: AsyncSession,
    query: str,
    *,
    top_k: int,
) -> List[RetrievedChunk]:
    """仅使用向量相似度的检索接口。"""
    if top_k <= 0 or not query.strip():
        return []

    embedder = get_embedder()
    query_embedding = (
        await run_in_threadpool(embedder.encode, [query], normalize_embeddings=True)
    )[0]

    vector_hits = await _vector_candidates(db, query_embedding, top_k)
    results = list(vector_hits.values())
    results.sort(key=lambda item: item.score, reverse=True)
    return results[:top_k]

async def _vector_candidates(
    db: AsyncSession,
    query_embedding: np.ndarray,
    top_k: int,
) -> Dict[int, RetrievedChunk]:
    """Fetch candidates using vector similarity search.
    使用向量相似度搜索获取候选者。
    """
    rows = await crud_knowledge_base.search_by_vector(
        db,
        query_embedding,
        top_k,
    )
    items: Dict[int, RetrievedChunk] = {}
    for chunk, distance in rows:
        distance_val = float(distance)
        # 将距离转换为相似度 (假设余弦距离)
        similarity = max(0.0, 1.0 - distance_val)
        items[chunk.id] = RetrievedChunk(
            chunk=chunk,
            score=similarity,
            similarity=similarity,
            retrieval_source="vector",
            vector_score=similarity,
            bm25_score=0.0,
        )
    return items


async def bm25_search(
    db: AsyncSession,
    query: str,
    *,
    requested_top_k: int,
) -> BM25SearchResult:
    """Perform BM25 keyword search.
    执行 BM25 关键词搜索。
    """
    return await _bm25_candidates(db, query, requested_top_k)


async def _bm25_candidates(
    db: AsyncSession,
    query: str,
    top_k: int,
) -> BM25SearchResult:
    """Fetch BM25 results with normalization."""
    config_map = await _load_dynamic_settings()
    bm25_config = build_bm25_config(config_map, requested_top_k=top_k)
    if not query.strip():
        return BM25SearchResult(matches=[], raw_hits=0, after_threshold=0)

    query_language = detect_language(query)
    rows = await crud_knowledge_base.search_by_bm25(
        db,
        query,
        bm25_config.top_k,
        query_language=query_language,
        min_rank=bm25_config.min_rank,
    )

    return _normalize_bm25_rows(rows)


def _merge_candidates(
    vector_hits: Dict[int, RetrievedChunk],
    bm25_hits: Dict[int, tuple["models.KnowledgeChunk", float, float]],
) -> List[RetrievedChunk]:
    """Merge vector and BM25 candidates (Hybrid Search).
    合并向量和 BM25 候选者 (混合搜索)。
    """
    merged: Dict[int, RetrievedChunk] = dict(vector_hits)

    for chunk_id, (chunk, normalized, raw_score) in bm25_hits.items():
        if chunk_id in merged:
            # 如果在向量结果中已存在，更新为混合模式
            item = merged[chunk_id]
            item.bm25_score = raw_score
            item.retrieval_source = "hybrid"
            # 取向量得分和 BM25 归一化得分的最大值作为基础得分
            candidate = max(item.vector_score, normalized)
            item.score = candidate
            item.similarity = max(item.similarity, normalized)
        else:
            # 如果仅在 BM25 结果中，添加为新条目
            merged[chunk_id] = RetrievedChunk(
                chunk=chunk,
                score=normalized,
                similarity=normalized,
                retrieval_source="bm25",
                vector_score=0.0,
                bm25_score=raw_score,
            )

    return list(merged.values())


async def hybrid_search(
    db: AsyncSession,
    query: str,
    top_k: int,
) -> List[RetrievedChunk]:
    """Fetch a generous batch of candidates via vector + BM25 and let Gemini digest them.
    通过向量 + BM25 获取大量候选者，并让 Gemini 进行处理。
    """
    if top_k <= 0 or not query.strip():
        return []

    config_map = await _load_dynamic_settings()
    rag_config = build_rag_config(config_map, requested_top_k=top_k)
    effective_top_k = rag_config.top_k

    # 生成查询向量
    embedder = get_embedder()
    query_embedding = (
        await run_in_threadpool(embedder.encode, [query], normalize_embeddings=True)
    )[0]

    # 获取向量检索候选者
    vector_hits = await _vector_candidates(
        db,
        query_embedding,
        effective_top_k,
    )
    # 获取 BM25 检索候选者
    bm25_result = await _bm25_candidates(db, query, effective_top_k)

    bm25_hits: Dict[int, tuple["models.KnowledgeChunk", float, float]] = {}
    for match in bm25_result.matches:
        bm25_hits[match.chunk.id] = (match.chunk, match.normalized_score, match.raw_score)

    # 合并结果
    merged = _merge_candidates(vector_hits, bm25_hits)

    # 按得分排序并截断
    merged.sort(key=lambda item: item.score, reverse=True)
    trimmed = merged[:effective_top_k]

    logger.debug(
        "retrieval simplified: vector=%s bm25=%s delivered=%s",
        len(vector_hits),
        len(bm25_hits),
        len(trimmed),
    )
    return trimmed


__all__ = [
    "BM25Match",
    "BM25SearchResult",
    "RetrievedChunk",
    "bm25_search",
    "vector_search",
    "hybrid_search",
]
