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
    # Only the retrieval breadth is admin configurable now.


class AdminSettingsResetRequest(BaseModel):
    """Payload for resetting one or more admin-configurable settings."""

    model_config = ConfigDict(extra="forbid")

    keys: list[str] | None = Field(
        default=None,
        description="Optional list of setting keys to reset. Reset all when omitted.",
    )
