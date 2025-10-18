from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Mapping, MutableMapping

from app.core.config import settings
from app.infrastructure.dynamic_settings import DynamicSettingsService
from app.infrastructure.utils.coerce_utils import coerce_bool

logger = logging.getLogger(__name__)

DynamicSettingsMapping = Mapping[str, Any]


async def resolve_dynamic_settings(
    service: DynamicSettingsService | None,
) -> dict[str, Any]:
    """Fetch dynamic settings via the service or fall back to defaults."""
    if service is None:
        return settings.dynamic_settings_defaults()

    if not hasattr(service, "get_all"):
        return settings.dynamic_settings_defaults()

    try:
        data = await service.get_all()
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("Dynamic settings service failed; using defaults")
        return settings.dynamic_settings_defaults()

    if not isinstance(data, (dict, MutableMapping)):
        logger.warning("Dynamic settings service returned non-dict payload; using defaults")
        return settings.dynamic_settings_defaults()

    return dict(data)


# --- Retrieval configuration -------------------------------------------------

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


def _read_setting(
    config_map: DynamicSettingsMapping | None,
    key: str,
    *,
    default: Any,
    caster: Callable[[Any], Any],
    minimum: Any | None = None,
    maximum: Any | None = None,
) -> Any:
    if not isinstance(config_map, Mapping):
        value = default
    else:
        value = config_map.get(key, default)

    try:
        candidate = caster(value)
    except (TypeError, ValueError):
        candidate = default

    if minimum is not None:
        candidate = candidate if candidate >= minimum else minimum
    if maximum is not None:
        candidate = candidate if candidate <= maximum else maximum
    return candidate


def build_rag_config(
    config_map: DynamicSettingsMapping | None,
    *,
    requested_top_k: int,
) -> RagSearchConfig:
    """Derive retrieval parameters from dynamic configuration."""
    base_top_k = max(1, requested_top_k)
    config_top_k = _read_setting(config_map, "RAG_TOP_K", default=settings.RAG_TOP_K, caster=int, minimum=1)
    effective_top_k = max(base_top_k, config_top_k)

    oversample_factor = _read_setting(
        config_map,
        "RAG_OVERSAMPLE",
        default=settings.RAG_OVERSAMPLE,
        caster=int,
        minimum=1,
    )
    limit_cap = _read_setting(
        config_map,
        "RAG_MAX_CANDIDATES",
        default=settings.RAG_MAX_CANDIDATES,
        caster=int,
        minimum=effective_top_k,
    )
    rerank_enabled = coerce_bool(
        config_map,
        "RAG_RERANK_ENABLED",
        settings.RAG_RERANK_ENABLED,
    )
    rerank_candidates = _read_setting(
        config_map,
        "RAG_RERANK_CANDIDATES",
        default=settings.RAG_RERANK_CANDIDATES,
        caster=int,
        minimum=effective_top_k,
    )
    rerank_score_threshold = _read_setting(
        config_map,
        "RAG_RERANK_SCORE_THRESHOLD",
        default=settings.RAG_RERANK_SCORE_THRESHOLD,
        caster=float,
        minimum=0.0,
        maximum=1.0,
    )
    rerank_max_batch = _read_setting(
        config_map,
        "RAG_RERANK_MAX_BATCH",
        default=settings.RAG_RERANK_MAX_BATCH,
        caster=int,
        minimum=1,
    )
    language_bonus = _read_setting(
        config_map,
        "RAG_SAME_LANG_BONUS",
        default=settings.RAG_SAME_LANG_BONUS,
        caster=float,
    )
    min_sim = _read_setting(
        config_map,
        "RAG_MIN_SIM",
        default=settings.RAG_MIN_SIM,
        caster=float,
        minimum=0.0,
        maximum=1.0,
    )
    mmr_lambda = _read_setting(
        config_map,
        "RAG_MMR_LAMBDA",
        default=settings.RAG_MMR_LAMBDA,
        caster=float,
        minimum=0.0,
        maximum=1.0,
    )
    per_doc_limit = _read_setting(
        config_map,
        "RAG_PER_DOC_LIMIT",
        default=settings.RAG_PER_DOC_LIMIT,
        caster=int,
        minimum=1,
    )
    bm25_enabled = coerce_bool(
        config_map,
        "BM25_ENABLED",
        settings.BM25_ENABLED,
    )
    bm25_top_k = _read_setting(
        config_map,
        "BM25_TOP_K",
        default=settings.BM25_TOP_K,
        caster=int,
        minimum=0,
    )
    bm25_weight = _read_setting(
        config_map,
        "BM25_WEIGHT",
        default=settings.BM25_WEIGHT,
        caster=float,
        minimum=0.0,
        maximum=1.0,
    )
    bm25_min_score = _read_setting(
        config_map,
        "BM25_MIN_SCORE",
        default=settings.BM25_MIN_SCORE,
        caster=float,
        minimum=0.0,
    )

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
        bm25_enabled=bm25_enabled,
        bm25_top_k=bm25_top_k,
        bm25_weight=bm25_weight,
        bm25_min_score=bm25_min_score,
    )


__all__ = ["DynamicSettingsMapping", "RagSearchConfig", "resolve_dynamic_settings", "build_rag_config"]
