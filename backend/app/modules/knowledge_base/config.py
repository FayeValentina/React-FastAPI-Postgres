from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Mapping, MutableMapping

from app.core.config import settings


# 获取日志记录器
logger = logging.getLogger(__name__)

# 类型别名，用于动态设置的映射
DynamicSettingsMapping = Mapping[str, Any]


# --- 检索配置 -------------------------------------------------

@dataclass(slots=True)
class RagSearchConfig:
    """Minimal retrieval configuration."""
    top_k: int


@dataclass(slots=True)
class BM25SearchConfig:
    """Configuration bundle for BM25-only search scenarios."""

    top_k: int
    min_rank: float


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
    """Construct the only parameter Gemini still needs: how many chunks to forward."""
    base_top_k = max(1, requested_top_k)
    config_top_k = _read_setting(
        config_map,
        "RAG_TOP_K",
        default=settings.RAG_TOP_K,
        caster=int,
        minimum=1,
    )
    effective = max(base_top_k, config_top_k)
    return RagSearchConfig(top_k=effective)


def build_bm25_config(
    config_map: DynamicSettingsMapping | None,
    *,
    requested_top_k: int,
) -> BM25SearchConfig:
    """Construct BM25 search configuration from request caps and dynamic min_rank."""

    top_k = max(1, min(requested_top_k, 100))
    min_rank = _read_setting(
        config_map,
        "BM25_MIN_RANK",
        default=settings.BM25_MIN_RANK,
        caster=float,
        minimum=0.0,
    )
    return BM25SearchConfig(
        top_k=top_k,
        min_rank=min_rank,
    )


# 导出模块内的主要类和函数
__all__ = [
    "BM25SearchConfig",
    "DynamicSettingsMapping",
    "RagSearchConfig",
    "build_bm25_config",
    "build_rag_config",
]
