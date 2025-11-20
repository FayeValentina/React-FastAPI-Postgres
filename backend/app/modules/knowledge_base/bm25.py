from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from . import models
from .repository import crud_knowledge_base


@dataclass(slots=True)
class BM25Match:
    """BM25 匹配结果的数据类"""
    chunk: models.KnowledgeChunk  # 知识库块
    raw_score: float  # 原始 BM25 分数
    normalized_score: float  # 归一化后的分数 (0-1范围)


@dataclass(slots=True)
class BM25SearchResult:
    """BM25 搜索结果的数据类"""
    matches: list[BM25Match]  # 匹配结果列表
    raw_hits: int  # 原始命中数量
    after_threshold: int  # 应用阈值后的命中数量
    max_score: float | None = None  # 最高原始分数
    min_score: float | None = None  # 最低原始分数


async def fetch_bm25_matches(
    db: AsyncSession,
    query: str,
    top_k: int,
    *,
    min_rank: float | None = None,
    language: Optional[str] = None,
) -> BM25SearchResult:
    """执行 BM25 搜索，返回匹配项和摘要统计信息。"""
    # 如果 top_k 小于等于 0 或者查询为空，则返回空结果
    if top_k <= 0 or not query.strip():
        return BM25SearchResult(matches=[], raw_hits=0, after_threshold=0)

    # 调用 CRUD 函数执行 BM25 搜索
    rows = await crud_knowledge_base.search_by_bm25(
        db,
        query,
        top_k,
        query_language=language,
        min_rank=min_rank,
    )

    # 如果没有结果，则返回空
    if not rows:
        return BM25SearchResult(
            matches=[],
            raw_hits=0,
            after_threshold=0,
        )

    # 提取原始分数，用于后续的归一化处理
    raw_scores = [float(score or 0.0) for _, score in rows]
    max_score = max(raw_scores)  # 计算最高分
    min_score_value = min(raw_scores)  # 计算最低分
    # 计算分母，用于归一化，避免除以零
    denom = max(max_score - min_score_value, 1e-6)

    matches: list[BM25Match] = []
    # 遍历搜索结果，创建 BM25Match 对象
    for chunk, score in rows:
        # 归一化分数到 0-1 范围
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
    
    # 返回最终的搜索结果
    return BM25SearchResult(
        matches=matches,
        raw_hits=len(rows),
        # gating 已在数据库层完成，此处 after_threshold 与 raw_hits 一致
        after_threshold=len(rows),
        max_score=max_score,
        min_score=min_score_value,
    )