# 从 __future__ 模块导入 annotations，用于支持延迟评估的类型注解
from __future__ import annotations

# 导入日志、数学、时间处理、集合和数据类等标准库
import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, List

# 导入 numpy 用于数值计算
import numpy as np
# 从 FastAPI 导入 run_in_threadpool 用于在线程池中运行阻塞代码
from fastapi.concurrency import run_in_threadpool
# 从 sqlalchemy 导入异步会话
from sqlalchemy.ext.asyncio import AsyncSession

# 导入当前目录下的模块
from . import models
from .bm25 import fetch_bm25_matches
from .config import (
    DynamicSettingsMapping,
    RagSearchConfig,
    build_rag_config,
)
from .embeddings import get_embedder, get_reranker
from .language import detect_language, lingua_status
from .repository import crud_knowledge_base

# 获取当前模块的 logger 实例
logger = logging.getLogger(__name__)

# 定义语言匹配的奖励分数，当查询和知识块语言相同时，给予此奖励
LANGUAGE_MATCH_BONUS = 0.12
# 定义重排序器处理的最大批次大小，以控制内存使用和计算效率
RERANK_MAX_BATCH = 16


# 使用 dataclass 装饰器定义一个数据类，用于存储检索到的知识块信息
@dataclass(slots=True)
class RetrievedChunk:
    """
    数据类，用于存储检索到的知识块及其相关信息。
    `slots=True` 优化了内存使用。
    """
    chunk: "models.KnowledgeChunk"  # 关联的知识块 ORM 模型实例
    distance: float  # 在向量空间中与查询向量的距离
    similarity: float  # 与查询的余弦相似度
    score: float  # 用于排序的综合分数
    embedding: np.ndarray  # 知识块的嵌入向量
    language_bonus: float = 0.0  # 如果语言匹配，获得的奖励分数
    coarse_score: float = 0.0  # 粗排阶段计算的分数（例如，向量相似度 + 语言奖励）
    mmr_score: float = 0.0  # 最大边际相关性（MMR）算法计算的分数
    rerank_score: float | None = None  # 交叉编码器重排序模型给出的分数
    bm25_score: float | None = None  # BM25 算法给出的分数
    retrieval_source: str = "vector"  # 检索来源，如 "vector", "bm25", 或 "hybrid"
    vector_score: float = 0.0  # 纯向量搜索产生的相似度分数


def _sigmoid(value: float) -> float:
    """
    计算给定值的 sigmoid 函数结果。
    用于将无界的重排序分数转换为 0 到 1 之间的概率值。
    """
    try:
        # 对正数和负数采用不同的计算方式以避免浮点数溢出
        if value >= 0:
            z = math.exp(-value)
            return 1.0 / (1.0 + z)
        z = math.exp(value)
        return z / (1.0 + z)
    except OverflowError:
        # 如果发生溢出，根据输入值的符号返回 0.0 或 1.0
        return 0.0 if value < 0 else 1.0


def _batched(items: Iterable[Any], size: int) -> Iterable[list[Any]]:
    """
    将一个可迭代对象分割成指定大小的批次。
    """
    batch: list[Any] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _build_rerank_preview(content: str, limit: int = 512) -> str:
    """
    为重排序器输入构建内容预览，尝试在句子边界处截断以保持语义完整性。
    这有助于在限制输入长度的同时，为重排序模型提供更有意义的上下文。
    """
    text = (content or "").strip()
    # 如果文本长度小于限制，直接返回
    if len(text) <= limit:
        return text

    cutoff = -1
    # 定义句子边界标记
    boundary_markers = ["\n", "。", "！", "!", "?", "？", "."]
    # 从后向前查找最近的句子边界
    for marker in boundary_markers:
        idx = text.rfind(marker, 0, limit)
        if idx > cutoff:
            cutoff = idx

    # 如果找到了一个合适的截断点（在 60% 长度之后），则在此处截断
    if cutoff >= int(limit * 0.6):
        return text[: cutoff + 1].strip()

    # 否则，硬截断到限制长度
    return text[:limit].rstrip()


def _mmr_select(
    candidates: List[RetrievedChunk],
    top_k: int,
    mmr_lambda: float,
    per_doc_limit: int,
) -> List[RetrievedChunk]:
    """
    使用最大边际相关性（MMR）算法从候选列表中选择多样化的结果。
    MMR 旨在平衡结果的相关性和多样性。
    """
    if top_k <= 0:
        return []
    selected: List[RetrievedChunk] = []
    remaining = candidates.copy()
    # 记录每个文档已选择的块数
    doc_counts: defaultdict[int | None, int] = defaultdict(int)

    while remaining and len(selected) < top_k:
        best_index = None
        best_score = float("-inf")
        for idx, candidate in enumerate(remaining):
            doc_id = candidate.chunk.document_id
            # 如果设置了单个文档块数限制，并且已达到限制，则跳过
            if doc_id is not None and per_doc_limit > 0 and doc_counts[doc_id] >= per_doc_limit:
                continue

            # 如果尚未选择任何块，MMR 分数就是其原始分数
            if not selected:
                mmr_score = candidate.score
            else:
                # 计算与已选块的最大相似度（冗余度）
                redundancy = max(
                    float(np.dot(candidate.embedding, chosen.embedding))
                    for chosen in selected
                )
                # MMR 公式：平衡相关性（candidate.score）和冗余度
                mmr_score = mmr_lambda * candidate.score - (1 - mmr_lambda) * redundancy

            if mmr_score > best_score:
                best_score = mmr_score
                best_index = idx

        if best_index is None:
            break

        # 选择最佳块并更新列表
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
    q_lang: str,  # 查询语言
    q_emb: np.ndarray,  # 查询的嵌入向量
    rag_config: RagSearchConfig,  # RAG 搜索配置
    candidate_map: dict[int, RetrievedChunk],  # 候选块的映射
    vector_candidates: int,  # 向量搜索候选者的数量
) -> dict[str, Any]:
    """
    应用 BM25 融合策略，将 BM25 的稀疏检索分数与向量搜索的密集检索结果结合。
    """
    stats: dict[str, Any] = {
        "bm25_weight": round(float(rag_config.bm25_weight), 4),
        "vector_candidates": vector_candidates,
    }

    normalized_scores: dict[int, float] = {}

    # 如果 BM25 top_k 小于等于 0 或查询为空，则不执行 BM25
    if not (rag_config.bm25_top_k > 0 and query.strip()):
        return stats

    # 获取 BM25 匹配结果
    search_result = await fetch_bm25_matches(
        db,
        query,
        rag_config.bm25_top_k,
        min_rank=rag_config.bm25_min_rank,
        language=q_lang,
        filters={},
    )
    stats["bm25_raw_hits"] = search_result.raw_hits
    stats["bm25_after_threshold"] = search_result.after_threshold

    if not search_result.matches:
        return stats

    if search_result.max_score is not None:
        stats["bm25_max_rank"] = float(search_result.max_score)
    if search_result.min_score is not None:
        stats["bm25_min_rank"] = float(search_result.min_score)

    # 遍历 BM25 匹配结果
    for match in search_result.matches:
        chunk = match.chunk
        raw_score = match.raw_score
        normalized = match.normalized_score
        normalized_scores[chunk.id] = normalized

        embedding_vector = np.asarray(chunk.embedding, dtype=np.float32)
        chunk_lang = (chunk.language or "").lower() if getattr(chunk, "language", None) else ""
        # 计算语言奖励
        language_bonus_value = LANGUAGE_MATCH_BONUS if q_lang and chunk_lang and chunk_lang == q_lang else 0.0
        # 估算向量相似度
        similarity_estimate = max(0.0, float(np.dot(q_emb, embedding_vector)))
        distance_estimate = max(0.0, 1.0 - similarity_estimate)
        # 混合分数计算
        combined_base = (1.0 - rag_config.bm25_weight) * similarity_estimate + rag_config.bm25_weight * normalized
        combined_base = max(0.0, min(1.0, combined_base))

        existing = candidate_map.get(chunk.id)
        if existing is None:
            # 如果是新的块（仅在 BM25 结果中），则创建新的 RetrievedChunk
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
            # 如果块已存在（在向量搜索结果中），则更新其分数
            existing.bm25_score = raw_score
            if rag_config.bm25_weight > 0:
                existing.retrieval_source = "hybrid"
            existing.vector_score = max(
                float(existing.vector_score), similarity_estimate
            )
            existing.similarity = max(
                float(existing.similarity), similarity_estimate
            )
            # 重新计算混合分数
            base_component = (1.0 - rag_config.bm25_weight) * float(
                existing.vector_score
            ) + rag_config.bm25_weight * normalized
            base_component = max(0.0, min(1.0, base_component))
            existing.coarse_score = base_component + existing.language_bonus
            existing.score = existing.coarse_score

    stats["bm25_fused"] = len(normalized_scores)

    # 如果 BM25 权重>0，重新计算所有候选块的分数
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
    config: DynamicSettingsMapping) -> List[RetrievedChunk]:
    """
    通过结合向量搜索、BM25、重排序和 MMR 来检索最匹配的知识块。
    这是 RAG 检索的核心函数。
    """
    if top_k <= 0:
        return []

    # 根据动态设置构建 RAG 配置
    rag_config = build_rag_config(config, requested_top_k=top_k)

    logger.debug("rag_lang_status %s", lingua_status(config))
    # 检测查询语言
    query_language = detect_language(query, config)
    # 获取嵌入模型
    embedder = get_embedder()
    # 为查询生成嵌入向量
    query_embedding = (await run_in_threadpool(embedder.encode, [query], normalize_embeddings=True))[0]

    # 计算需要检索的候选块数量（过采样）
    oversample = max(top_k * rag_config.oversample_factor, top_k)
    if rag_config.rerank_enabled:
        oversample = max(oversample, rag_config.rerank_candidates)
    # 限制最终检索数量
    limit = min(rag_config.limit_cap, oversample)

    # 记录 RAG 搜索参数
    logger.info(
        (
            "rag_search_params top_k=%s oversample_factor=%s limit_cap=%s effective_limit=%s "
            "min_sim=%.4f mmr_lambda=%.4f per_doc_limit=%s rerank_enabled=%s rerank_candidates=%s "
            "rerank_threshold=%.4f bm25_top_k=%s bm25_weight=%.3f bm25_min_rank=%.3f"
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
        rag_config.bm25_min_rank,
    )

    # 从数据库中通过向量相似度获取候选块
    rows = await crud_knowledge_base.fetch_chunk_candidates_by_embedding(db, query_embedding, limit)

    candidates: List[RetrievedChunk] = []
    # 处理向量搜索结果
    for chunk, distance in rows:
        distance_val = float(distance)
        similarity = max(0.0, 1.0 - distance_val)
        base_score = similarity
        language_bonus_value = 0.0
        chunk_lang = (chunk.language or "").lower() if getattr(chunk, "language", None) else ""
        # 如果查询和块的语言匹配，则添加奖励
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

    # 根据最小相似度阈值过滤候选块
    filtered = [item for item in candidates if item.similarity >= rag_config.min_sim]
    candidate_map: dict[int, RetrievedChunk] = {item.chunk.id: item for item in filtered}
    vector_candidates_count = len(filtered)

    # 应用 BM25 融合
    bm25_stats = await _apply_bm25_fusion(
        db,
        query,
        q_lang=query_language,
        q_emb=query_embedding,
        rag_config=rag_config,
        candidate_map=candidate_map,
        vector_candidates=vector_candidates_count,
    )

    # 获取融合后的候选块列表并按分数排序
    filtered = list(candidate_map.values())
    filtered.sort(key=lambda item: item.score, reverse=True)

    if not filtered:
        return []

    rerank_stats: dict[str, Any] = {}

    # 如果启用了重排序，则执行重排序
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
            # 准备重排序器的输入（查询-文本对）
            for item in head:
                content = getattr(item.chunk, "content", "") or ""
                preview = _build_rerank_preview(content)
                pairs.append([query, preview])

            # 分批进行重排序预测
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
            (time.perf_counter() - start_time) * 1000,
            3
        )

        if rerank_scores:
            # 将重排序分数转换为概率
            probabilities = [_sigmoid(score) for score in rerank_scores]
            above_threshold = sum(
                prob >= rag_config.rerank_score_threshold for prob in probabilities
            )
            # 更新块的分数
            for item, prob in zip(head, probabilities):
                item.rerank_score = prob
                coarse_without_bonus = max(0.0, item.coarse_score - item.language_bonus)
                adjusted = prob
                # 如果分数低于阈值，则进行平滑处理
                if prob < rag_config.rerank_score_threshold:
                    adjusted = (prob + coarse_without_bonus) / 2.0
                item.score = adjusted + item.language_bonus

            # 对于没有重排序分数的块，使用粗排分数
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
            # 如果重排序失败，则所有块都使用粗排分数
            for item in head:
                item.score = item.coarse_score
                item.rerank_score = None

        # 合并重排序过的和未重排序的块，并重新排序
        filtered = head + tail
        filtered.sort(key=lambda item: item.score, reverse=True)

    # 应用 MMR 算法进行多样性选择
    selected = _mmr_select(filtered, top_k, rag_config.mmr_lambda, rag_config.per_doc_limit)

    if not selected:
        return []

    # 按 MMR 分数、综合分数和相似度进行最终排序
    selected.sort(key=lambda item: (item.mmr_score, item.score, item.similarity), reverse=True)

    # 记录检索过程的详细统计信息
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


# 导出公共接口
__all__ = ["RetrievedChunk", "search_similar_chunks"]
