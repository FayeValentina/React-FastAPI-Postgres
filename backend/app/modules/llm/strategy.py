from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional

from app.core.config import settings
from app.modules.llm import intent_classifier


@dataclass(slots=True)
class StrategyContext:
    top_k_request: Optional[int] = None
    document_id: Optional[int] = None
    channel: str = "rest"
    user_role: Optional[str] = None
    metadata: Mapping[str, Any] | None = None


@dataclass(slots=True)
class StrategyResult:
    config: Dict[str, Any]
    router_decision: intent_classifier.RouterDecision
    processed_query: str | None = None
    scenario: str = field(default="search")


def _resolve_top_k(
    base_config: Mapping[str, Any],
    requested: Optional[int],
) -> int:
    base = base_config.get("RAG_TOP_K", settings.RAG_TOP_K)
    try:
        base_value = int(base)
    except (TypeError, ValueError):
        base_value = settings.RAG_TOP_K

    if requested is None:
        return max(1, base_value)

    return max(1, max(base_value, requested))


async def resolve_rag_parameters(
    query: str,
    base_config: Mapping[str, Any],
    *,
    request_ctx: StrategyContext,
) -> StrategyResult:
    decision = await intent_classifier.route_query(query, request_ctx)
    top_k = _resolve_top_k(base_config, request_ctx.top_k_request)
    merged = {"RAG_TOP_K": top_k}

    processed_query = decision.search_query if decision.mode == "search" else query

    return StrategyResult(
        config=merged,
        router_decision=decision,
        processed_query=processed_query,
        scenario=decision.mode,
    )


__all__ = ["StrategyContext", "StrategyResult", "resolve_rag_parameters"]
