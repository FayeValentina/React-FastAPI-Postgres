from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Mapping, MutableMapping

from app.core.config import settings
from app.infrastructure.dynamic_settings import DynamicSettingsService
from app.infrastructure.utils.coerce_utils import coerce_bool

# 获取日志记录器
logger = logging.getLogger(__name__)

# 类型别名，用于动态设置的映射
DynamicSettingsMapping = Mapping[str, Any]


async def resolve_dynamic_settings(
    service: DynamicSettingsService | None,
) -> dict[str, Any]:
    """通过服务获取动态设置，如果失败则回退到默认值。"""
    # 如果服务为空，返回默认动态设置
    if service is None:
        return settings.dynamic_settings_defaults()

    # 检查服务是否具有 get_all 方法
    if not hasattr(service, "get_all"):
        return settings.dynamic_settings_defaults()

    try:
        # 尝试从服务获取所有动态设置
        data = await service.get_all()
    except Exception:  # pragma: no cover - defensive logging
        # 记录异常并返回默认设置
        logger.exception("动态设置服务失败；使用默认值")
        return settings.dynamic_settings_defaults()

    # 检查返回的数据是否为字典或可变映射
    if not isinstance(data, (dict, MutableMapping)):
        logger.warning("动态设置服务返回了非字典负载；使用默认值")
        return settings.dynamic_settings_defaults()

    # 返回获取到的动态设置
    return dict(data)


# --- 检索配置 -------------------------------------------------

@dataclass(slots=True)
class RagSearchConfig:
    """RAG 搜索配置的数据类"""
    effective_top_k: int  # 生效的 top_k 值
    oversample_factor: int  # 过采样因子
    limit_cap: int  # 候选结果数量上限
    rerank_enabled: bool  # 是否启用重排
    rerank_candidates: int  # 重排候选结果数量
    rerank_score_threshold: float  # 重排分数阈值
    min_sim: float  # 最小相似度
    mmr_lambda: float  # MMR (Maximal Marginal Relevance) 的 lambda 参数
    per_doc_limit: int  # 每个文档的限制
    bm25_top_k: int  # BM25 检索的 top_k 值
    bm25_weight: float  # BM25 的权重
    bm25_min_rank: float  # BM25 的最低排名


def _read_setting(
    config_map: DynamicSettingsMapping | None,
    key: str,
    *,
    default: Any,
    caster: Callable[[Any], Any],
    minimum: Any | None = None,
    maximum: Any | None = None,
) -> Any:
    """从配置映射中读取、转换和验证设置项。"""
    # 如果配置映射不是一个有效的映射，则使用默认值
    if not isinstance(config_map, Mapping):
        value = default
    else:
        # 从配置映射中获取值，如果键不存在则使用默认值
        value = config_map.get(key, default)

    try:
        # 尝试使用提供的 caster 函数转换值
        candidate = caster(value)
    except (TypeError, ValueError):
        # 如果转换失败，则使用默认值
        candidate = default

    # 如果设置了最小值，则确保值不小于最小值
    if minimum is not None:
        candidate = candidate if candidate >= minimum else minimum
    # 如果设置了最大值，则确保值不大于最大值
    if maximum is not None:
        candidate = candidate if candidate <= maximum else maximum
    return candidate


def build_rag_config(
    config_map: DynamicSettingsMapping | None,
    *,
    requested_top_k: int,
) -> RagSearchConfig:
    """根据动态配置派生检索参数。"""
    # 确定基础 top_k 值
    base_top_k = max(1, requested_top_k)
    # 从配置中读取 RAG_TOP_K，并确保其不小于1
    config_top_k = _read_setting(config_map, "RAG_TOP_K", default=settings.RAG_TOP_K, caster=int, minimum=1)
    # 生效的 top_k 取请求值和配置值中的较大者
    effective_top_k = max(base_top_k, config_top_k)

    # 读取过采样因子
    oversample_factor = _read_setting(
        config_map,
        "RAG_OVERSAMPLE",
        default=settings.RAG_OVERSAMPLE,
        caster=int,
        minimum=1,
    )
    # 读取候选结果数量上限
    limit_cap = _read_setting(
        config_map,
        "RAG_MAX_CANDIDATES",
        default=settings.RAG_MAX_CANDIDATES,
        caster=int,
        minimum=effective_top_k,
    )
    # 读取是否启用重排
    rerank_enabled = coerce_bool(
        config_map,
        "RAG_RERANK_ENABLED",
        settings.RAG_RERANK_ENABLED,
    )
    # 读取重排候选结果数量
    rerank_candidates = _read_setting(
        config_map,
        "RAG_RERANK_CANDIDATES",
        default=settings.RAG_RERANK_CANDIDATES,
        caster=int,
        minimum=effective_top_k,
    )
    # 读取重排分数阈值
    rerank_score_threshold = _read_setting(
        config_map,
        "RAG_RERANK_SCORE_THRESHOLD",
        default=settings.RAG_RERANK_SCORE_THRESHOLD,
        caster=float,
        minimum=0.0,
        maximum=1.0,
    )
    # 读取最小相似度
    min_sim = _read_setting(
        config_map,
        "RAG_MIN_SIM",
        default=settings.RAG_MIN_SIM,
        caster=float,
        minimum=0.0,
        maximum=1.0,
    )
    # 读取 MMR 的 lambda 参数
    mmr_lambda = _read_setting(
        config_map,
        "RAG_MMR_LAMBDA",
        default=settings.RAG_MMR_LAMBDA,
        caster=float,
        minimum=0.0,
        maximum=1.0,
    )
    # 读取每个文档的限制
    per_doc_limit = _read_setting(
        config_map,
        "RAG_PER_DOC_LIMIT",
        default=settings.RAG_PER_DOC_LIMIT,
        caster=int,
        minimum=1,
    )
    # 读取 BM25 的 top_k 值
    bm25_top_k = _read_setting(
        config_map,
        "BM25_TOP_K",
        default=settings.BM25_TOP_K,
        caster=int,
        minimum=0,
    )
    # 读取 BM25 的权重
    bm25_weight = _read_setting(
        config_map,
        "BM25_WEIGHT",
        default=settings.BM25_WEIGHT,
        caster=float,
        minimum=0.0,
        maximum=1.0,
    )
    # 读取 BM25 的最低排名
    bm25_min_rank = _read_setting(
        config_map, "BM25_MIN_RANK",
        default=settings.BM25_MIN_RANK, caster=float, minimum=0.0
    )

    # 返回构建好的 RAG 搜索配置
    return RagSearchConfig(
        effective_top_k=effective_top_k,
        oversample_factor=oversample_factor,
        limit_cap=limit_cap,
        rerank_enabled=rerank_enabled,
        rerank_candidates=rerank_candidates,
        rerank_score_threshold=rerank_score_threshold,
        min_sim=min_sim,
        mmr_lambda=mmr_lambda,
        per_doc_limit=per_doc_limit,
        bm25_top_k=bm25_top_k,
        bm25_weight=bm25_weight,
        bm25_min_rank=bm25_min_rank,
    )


# 导出模块内的主要类和函数
__all__ = ["DynamicSettingsMapping", "RagSearchConfig", "resolve_dynamic_settings", "build_rag_config"]