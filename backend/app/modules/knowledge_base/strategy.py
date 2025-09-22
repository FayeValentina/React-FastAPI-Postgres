from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

from app.core.config import settings
from app.modules.knowledge_base import intent_classifier


logger = logging.getLogger(__name__)


def _safe_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else fallback
    except (TypeError, ValueError):
        return fallback


def _safe_float(value: Any, fallback: float, *, minimum: float | None = None, maximum: float | None = None) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = fallback
    if minimum is not None and parsed < minimum:
        parsed = minimum
    if maximum is not None and parsed > maximum:
        parsed = maximum
    return parsed


def _safe_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return fallback


LLM_SCENARIO_MAP: Dict[str, str] = {
    "broad": "broad",
    "overview": "broad",
    "summary": "broad",
    "compare": "broad",
    "comparison": "broad",
    "precise": "precise",
    "specific": "precise",
    "lookup": "precise",
    "procedural": "precise",
    "step_by_step": "precise",
    "question": "question",
    "qa": "question",
    "troubleshooting": "question",
    "diagnosis": "question",
    "document_focus": "document_focus",
    "document": "document_focus",
    "doc": "document_focus",
    "default": "default",
}


def _select_llm_scenario(result: intent_classifier.ClassificationResult) -> Tuple[str | None, str | None]:
    candidates: list[str] = []
    if result.scenario:
        candidates.append(result.scenario.lower())
    candidates.extend(tag.lower() for tag in result.tags)

    for label in candidates:
        mapped = LLM_SCENARIO_MAP.get(label)
        if mapped:
            return mapped, label
    if candidates:
        return None, candidates[0]
    return None, None


@dataclass(slots=True)
class StrategyContext:
    top_k_request: Optional[int] = None
    document_id: Optional[int] = None
    channel: str = "rest"
    user_role: Optional[str] = None
    metadata: Mapping[str, Any] | None = None

    def to_log_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "channel": self.channel,
            "top_k_request": self.top_k_request,
            "document_id": self.document_id,
            "user_role": self.user_role,
        }
        if self.metadata:
            payload["metadata_keys"] = sorted(self.metadata.keys())
        return payload


@dataclass(slots=True)
class StrategyResult:
    config: Dict[str, Any]
    overrides: Dict[str, Any] = field(default_factory=dict)
    scenario: str = "default"
    context: StrategyContext | None = None
    error: str | None = None
    classifier: Dict[str, Any] | None = None

    def to_log_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "scenario": self.scenario,
            "overrides": self.overrides,
        }
        if self.context:
            payload["context"] = self.context.to_log_dict()
        if self.error:
            payload["error"] = self.error
        if self.classifier:
            payload["classifier"] = self.classifier
        return payload


def _classify_query(query: str, ctx: StrategyContext) -> str:
    normalized = (query or "").strip().lower()
    if not normalized:
        return "empty"

    if ctx.document_id is not None:
        return "document_focus"

    broad_keywords = {"overview", "introduce", "introduce all", "列表", "介绍", "总结", "all", "全部"}
    if any(token in normalized for token in broad_keywords):
        return "broad"

    words = re.findall(r"\w+", normalized)
    if len(words) >= 12:
        return "broad"

    precise_hints = ('"', "'", "`", "::", "/", "\\", "#", ".")
    if len(words) <= 4 or any(hint in normalized for hint in precise_hints):
        return "precise"

    if "?" in normalized:
        return "question"

    return "default"


def _apply_scenario(
    scenario: str,
    base_top_k: int,
    base_per_doc: int,
    base_min_sim: float,
    base_oversample: int,
    base_max_candidates: int,
    base_rerank_candidates: int,
    base_rerank_threshold: float,
    base_context_max_evidence: int,
    base_context_budget: int,
    ctx: StrategyContext,
) -> Dict[str, Any]:
    request_top_k = _safe_int(ctx.top_k_request, base_top_k) if ctx.top_k_request else base_top_k
    overrides: Dict[str, Any] = {}

    if scenario == "broad":
        top_k_target = max(base_top_k, request_top_k)
        top_k_target = min(top_k_target + 4, 12)
        overrides["RAG_TOP_K"] = top_k_target
        overrides["RAG_PER_DOC_LIMIT"] = max(base_per_doc, 3)
        overrides["RAG_MIN_SIM"] = max(0.2, base_min_sim - 0.1)
        overrides["RAG_OVERSAMPLE"] = max(base_oversample, 7)
        overrides["RAG_MAX_CANDIDATES"] = max(base_max_candidates, top_k_target * 12)
        overrides["RAG_RERANK_CANDIDATES"] = max(base_rerank_candidates, top_k_target * 6)
        overrides["RAG_RERANK_SCORE_THRESHOLD"] = min(base_rerank_threshold, 0.45)
        overrides["RAG_CONTEXT_MAX_EVIDENCE"] = max(base_context_max_evidence, 18)
        overrides["RAG_CONTEXT_TOKEN_BUDGET"] = max(base_context_budget, 2800)
    elif scenario == "precise":
        top_k_target = min(base_top_k, request_top_k)
        top_k_target = max(3, top_k_target - 2)
        overrides["RAG_TOP_K"] = top_k_target
        overrides["RAG_PER_DOC_LIMIT"] = max(base_per_doc, 5)
        overrides["RAG_MIN_SIM"] = min(0.9, base_min_sim + 0.15)
        overrides["RAG_OVERSAMPLE"] = max(1, min(base_oversample, 3))
        overrides["RAG_MAX_CANDIDATES"] = max(top_k_target * 3, min(base_max_candidates, 80))
        overrides["RAG_RERANK_CANDIDATES"] = max(top_k_target, min(base_rerank_candidates, top_k_target * 3))
        overrides["RAG_RERANK_SCORE_THRESHOLD"] = min(base_rerank_threshold, 0.55)
        overrides["RAG_CONTEXT_MAX_EVIDENCE"] = max(6, min(base_context_max_evidence, 10))
        overrides["RAG_CONTEXT_TOKEN_BUDGET"] = max(1200, min(base_context_budget, 1800))
    elif scenario == "document_focus":
        overrides["RAG_PER_DOC_LIMIT"] = max(base_per_doc, 6)
        top_k_target = max(base_top_k, min(request_top_k, 8))
        overrides["RAG_TOP_K"] = top_k_target
        overrides["RAG_MIN_SIM"] = min(0.85, max(base_min_sim, 0.6))
        overrides["RAG_OVERSAMPLE"] = max(base_oversample, 6)
        max_candidates_target = max(base_max_candidates, 160)
        overrides["RAG_MAX_CANDIDATES"] = max_candidates_target
        rerank_target = max(
            base_rerank_candidates,
            min(max_candidates_target, max(top_k_target * 6, 80)),
        )
        overrides["RAG_RERANK_CANDIDATES"] = rerank_target
        overrides["RAG_CONTEXT_MAX_EVIDENCE"] = max(base_context_max_evidence, 16)
        overrides["RAG_CONTEXT_TOKEN_BUDGET"] = max(base_context_budget, 2600)
    elif scenario == "question":
        top_k_target = max(base_top_k, min(request_top_k + 2, 10))
        overrides["RAG_TOP_K"] = top_k_target
        overrides["RAG_PER_DOC_LIMIT"] = max(base_per_doc, 4)
        overrides["RAG_OVERSAMPLE"] = max(base_oversample, 5)
        overrides["RAG_MAX_CANDIDATES"] = max(base_max_candidates, top_k_target * 10)
        overrides["RAG_RERANK_CANDIDATES"] = max(base_rerank_candidates, top_k_target * 5)
        overrides["RAG_RERANK_SCORE_THRESHOLD"] = min(base_rerank_threshold, 0.5)
        overrides["RAG_CONTEXT_MAX_EVIDENCE"] = max(base_context_max_evidence, 14)
        overrides["RAG_CONTEXT_TOKEN_BUDGET"] = max(base_context_budget, 2400)

    return overrides


def _sanitize_overrides(base: Mapping[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {}
    for key, value in overrides.items():
        if key == "RAG_TOP_K":
            candidate = _safe_int(value, _safe_int(base.get(key), settings.RAG_TOP_K))
            candidate = min(candidate, 50)
            if candidate > 0 and candidate != base.get(key):
                sanitized[key] = candidate
        elif key in {
            "RAG_PER_DOC_LIMIT",
            "RAG_OVERSAMPLE",
            "RAG_MAX_CANDIDATES",
            "RAG_RERANK_CANDIDATES",
            "RAG_CONTEXT_MAX_EVIDENCE",
            "RAG_CONTEXT_TOKEN_BUDGET",
        }:
            candidate = _safe_int(value, _safe_int(base.get(key), 1))
            if candidate >= 0 and candidate != base.get(key):
                sanitized[key] = candidate
        elif key == "RAG_MIN_SIM":
            candidate = _safe_float(value, _safe_float(base.get(key), settings.RAG_MIN_SIM), minimum=0.0, maximum=0.99)
            if candidate != base.get(key):
                sanitized[key] = round(candidate, 4)
        elif key == "RAG_RERANK_SCORE_THRESHOLD":
            candidate = _safe_float(
                value,
                _safe_float(base.get(key), settings.RAG_RERANK_SCORE_THRESHOLD),
                minimum=0.0,
                maximum=1.0,
            )
            if candidate != base.get(key):
                sanitized[key] = round(candidate, 4)
        else:
            sanitized[key] = value
    return sanitized


async def resolve_rag_parameters(
    query: str,
    base_config: Mapping[str, Any],
    *,
    request_ctx: StrategyContext,
) -> StrategyResult:
    base = dict(base_config)

    try:
        if not base.get("RAG_STRATEGY_ENABLED"):
            return StrategyResult(config=base, scenario="disabled", context=request_ctx)

        classifier_meta: Dict[str, Any] | None = None
        scenario: str | None = None

        classifier_enabled = _safe_bool(
            base.get("RAG_STRATEGY_LLM_CLASSIFIER_ENABLED"),
            settings.RAG_STRATEGY_LLM_CLASSIFIER_ENABLED,
        )

        if classifier_enabled:
            threshold = _safe_float(
                base.get("RAG_STRATEGY_LLM_CLASSIFIER_CONFIDENCE_THRESHOLD"),
                settings.RAG_STRATEGY_LLM_CLASSIFIER_CONFIDENCE_THRESHOLD,
                minimum=0.0,
                maximum=1.0,
            )

            classifier_result = await intent_classifier.classify(query, request_ctx)
            classifier_meta = classifier_result.to_log_dict()
            classifier_meta["threshold"] = round(threshold, 4)

            mapped_scenario, matched_label = _select_llm_scenario(classifier_result)

            if classifier_result.fallback:
                classifier_meta["applied"] = False
                logger.warning(
                    "llm classifier fallback; using heuristic classification",
                )
            elif mapped_scenario and (
                classifier_result.confidence is None or classifier_result.confidence >= threshold
            ):
                scenario = mapped_scenario
                classifier_meta["applied"] = True
                if matched_label:
                    classifier_meta["label"] = matched_label
            elif mapped_scenario:
                classifier_meta["applied"] = False
                if matched_label:
                    classifier_meta["label"] = matched_label
                classifier_meta["cause"] = "low_confidence"
                logger.warning(
                    "llm classifier confidence %.3f below threshold %.3f; using heuristic",
                    classifier_result.confidence or 0.0,
                    threshold,
                )
            else:
                classifier_meta["applied"] = False
                if matched_label:
                    classifier_meta["label"] = matched_label
                classifier_meta["cause"] = "unmapped_label"

        if scenario is None:
            scenario = _classify_query(query, request_ctx)

        base_top_k = _safe_int(base.get("RAG_TOP_K"), settings.RAG_TOP_K)
        base_per_doc = _safe_int(base.get("RAG_PER_DOC_LIMIT"), settings.RAG_PER_DOC_LIMIT)
        base_min_sim = _safe_float(base.get("RAG_MIN_SIM"), settings.RAG_MIN_SIM, minimum=0.0, maximum=1.0)
        base_oversample = _safe_int(base.get("RAG_OVERSAMPLE"), settings.RAG_OVERSAMPLE)
        base_max_candidates = _safe_int(base.get("RAG_MAX_CANDIDATES"), settings.RAG_MAX_CANDIDATES)
        base_rerank_candidates = _safe_int(base.get("RAG_RERANK_CANDIDATES"), settings.RAG_RERANK_CANDIDATES)
        base_rerank_threshold = _safe_float(
            base.get("RAG_RERANK_SCORE_THRESHOLD"),
            settings.RAG_RERANK_SCORE_THRESHOLD,
            minimum=0.0,
            maximum=1.0,
        )
        base_context_max_evidence = _safe_int(
            base.get("RAG_CONTEXT_MAX_EVIDENCE"),
            settings.RAG_CONTEXT_MAX_EVIDENCE,
        )
        base_context_budget = _safe_int(
            base.get("RAG_CONTEXT_TOKEN_BUDGET"),
            settings.RAG_CONTEXT_TOKEN_BUDGET,
        )

        overrides = _apply_scenario(
            scenario,
            base_top_k,
            base_per_doc,
            base_min_sim,
            base_oversample,
            base_max_candidates,
            base_rerank_candidates,
            base_rerank_threshold,
            base_context_max_evidence,
            base_context_budget,
            request_ctx,
        )
        sanitized = _sanitize_overrides(base, overrides)

        merged = dict(base)
        merged.update(sanitized)

        return StrategyResult(
            config=merged,
            overrides=sanitized,
            scenario=scenario,
            context=request_ctx,
            classifier=classifier_meta,
        )

    except Exception as exc:  # pragma: no cover - safety net
        logger.warning("resolve_rag_parameters failed: %s", exc, exc_info=logger.isEnabledFor(logging.DEBUG))
        return StrategyResult(config=base, scenario="error", context=request_ctx, error=str(exc))
