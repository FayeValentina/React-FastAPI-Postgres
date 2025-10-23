from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from . import models
from .repository import crud_knowledge_base


@dataclass(slots=True)
class BM25Match:
    chunk: models.KnowledgeChunk
    raw_score: float
    normalized_score: float


@dataclass(slots=True)
class BM25SearchResult:
    matches: list[BM25Match]
    raw_hits: int
    after_threshold: int
    max_score: float | None = None
    min_score: float | None = None


async def fetch_bm25_matches(
    db: AsyncSession,
    query: str,
    top_k: int,
    *,
    min_score: float = 0.0,
    language: Optional[str] = None,
    filters: Optional[dict] = None,
) -> BM25SearchResult:
    """Run BM25 search returning matches and summary stats."""
    if top_k <= 0 or not query.strip():
        return BM25SearchResult(matches=[], raw_hits=0, after_threshold=0)

    rows = await crud_knowledge_base.search_by_bm25(
        db,
        query,
        top_k,
        filters=filters or {},
        query_language=language,
    )

    filtered: list[tuple[models.KnowledgeChunk, float]] = []
    for chunk, raw_score in rows:
        score_value = float(raw_score or 0.0)
        if score_value < min_score:
            continue
        filtered.append((chunk, score_value))

    if not filtered:
        return BM25SearchResult(
            matches=[],
            raw_hits=len(rows),
            after_threshold=0,
        )

    raw_scores = [score for _, score in filtered]
    max_score = max(raw_scores)
    min_score_value = min(raw_scores)
    denom = max(max_score - min_score_value, 1e-6)

    matches: list[BM25Match] = []
    for chunk, score in filtered:
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
        after_threshold=len(matches),
        max_score=max_score,
        min_score=min_score_value,
    )


def to_numpy_embedding(chunk: models.KnowledgeChunk) -> np.ndarray:
    """Convert chunk embedding to numpy array (float32)."""
    return np.array(chunk.embedding, dtype=np.float32)
