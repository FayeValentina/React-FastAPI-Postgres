from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal

from pydantic import BaseModel, ConfigDict, Field


class AdminSettingsResponse(BaseModel):
    defaults: Dict[str, Any]
    overrides: Dict[str, Any]
    effective: Dict[str, Any]
    updated_at: datetime | None = None
    redis_status: Literal["ok", "unavailable"] = "ok"


class AdminSettingsUpdate(BaseModel):
    """Allow partial updates while enforcing sensible bounds for each field."""

    model_config = ConfigDict(extra="forbid")

    RAG_TOP_K: int | None = Field(None, ge=1, le=100)
    RAG_STRATEGY_ENABLED: bool | None = None
    RAG_MIN_SIM: float | None = Field(None, ge=0.0, le=1.0)
    RAG_MMR_LAMBDA: float | None = Field(None, ge=0.0, le=1.0)
    RAG_PER_DOC_LIMIT: int | None = Field(None, ge=0)
    RAG_OVERSAMPLE: int | None = Field(None, ge=1)
    RAG_MAX_CANDIDATES: int | None = Field(None, ge=1)
    RAG_RERANK_ENABLED: bool | None = None
    RAG_RERANK_CANDIDATES: int | None = Field(None, ge=1)
    RAG_RERANK_SCORE_THRESHOLD: float | None = Field(None, ge=0.0, le=1.0)
    RAG_CONTEXT_TOKEN_BUDGET: int | None = Field(None, ge=0)
    RAG_CONTEXT_MAX_EVIDENCE: int | None = Field(None, ge=0)
    RAG_IVFFLAT_PROBES: int | None = Field(None, ge=1)
    RAG_USE_LINGUA: bool | None = None
    RAG_STRATEGY_LLM_CLASSIFIER_CONFIDENCE_THRESHOLD: float | None = Field(None, ge=0.0, le=1.0)
    BM25_TOP_K: int | None = Field(None, ge=0)
    BM25_WEIGHT: float | None = Field(None, ge=0.0, le=1.0)
    BM25_MIN_SCORE: float | None = Field(None, ge=0.0)


class AdminSettingsResetRequest(BaseModel):
    """Payload for resetting one or more admin-configurable settings."""

    model_config = ConfigDict(extra="forbid")

    keys: list[str] | None = Field(
        default=None,
        description="Optional list of setting keys to reset. Reset all when omitted.",
    )
