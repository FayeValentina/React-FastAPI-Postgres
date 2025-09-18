from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import verify_internal_access
from app.infrastructure.dynamic_settings import (
    DynamicSettingsService,
    get_dynamic_settings_service,
)


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
    RAG_MIN_SIM: float | None = Field(None, ge=0.0, le=1.0)
    RAG_MMR_LAMBDA: float | None = Field(None, ge=0.0, le=1.0)
    RAG_PER_DOC_LIMIT: int | None = Field(None, ge=0)
    RAG_OVERSAMPLE: int | None = Field(None, ge=1)
    RAG_MAX_CANDIDATES: int | None = Field(None, ge=1)
    RAG_SAME_LANG_BONUS: float | None = Field(None, ge=0.0, le=5.0)
    RAG_CONTEXT_TOKEN_BUDGET: int | None = Field(None, ge=0)
    RAG_CONTEXT_MAX_EVIDENCE: int | None = Field(None, ge=0)
    RAG_CHUNK_TARGET_TOKENS_EN: int | None = Field(None, ge=1)
    RAG_CHUNK_TARGET_TOKENS_CJK: int | None = Field(None, ge=1)
    RAG_CHUNK_TARGET_TOKENS_DEFAULT: int | None = Field(None, ge=1)
    RAG_CHUNK_OVERLAP_RATIO: float | None = Field(None, ge=0.0, le=1.0)
    RAG_CODE_CHUNK_MAX_LINES: int | None = Field(None, ge=1)
    RAG_CODE_CHUNK_OVERLAP_LINES: int | None = Field(None, ge=0)


router = APIRouter(
    prefix="/admin/settings",
    tags=["admin-settings"],
    dependencies=[Depends(verify_internal_access)],
)


def _normalize_overrides(overrides: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for key, value in overrides.items():
        if key in defaults and defaults[key] == value:
            continue
        normalized[key] = value
    return normalized


def _parse_updated_at(raw: Any) -> datetime | None:
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None
    return None


@router.get("/", response_model=AdminSettingsResponse)
async def read_admin_settings(
    dynamic_settings_service: DynamicSettingsService = Depends(get_dynamic_settings_service),
) -> AdminSettingsResponse:
    defaults = dynamic_settings_service.defaults()

    effective = await dynamic_settings_service.get_all()

    redis_status: Literal["ok", "unavailable"] = "ok"
    try:
        overrides = await dynamic_settings_service.get_overrides()
    except Exception:
        overrides = {}
        redis_status = "unavailable"

    metadata = await dynamic_settings_service.get_metadata()
    updated_at = _parse_updated_at(metadata.get("updated_at")) if metadata else None

    normalized_overrides = _normalize_overrides(overrides, defaults)

    return AdminSettingsResponse(
        defaults=defaults,
        overrides=normalized_overrides,
        effective=effective,
        updated_at=updated_at,
        redis_status=redis_status,
    )


@router.put("/", response_model=AdminSettingsResponse)
async def update_admin_settings(
    payload: AdminSettingsUpdate,
    dynamic_settings_service: DynamicSettingsService = Depends(get_dynamic_settings_service),
) -> AdminSettingsResponse:
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No settings provided")

    effective = await dynamic_settings_service.update(updates)

    defaults = dynamic_settings_service.defaults()
    redis_status: Literal["ok", "unavailable"] = "ok"
    try:
        overrides = await dynamic_settings_service.get_overrides()
    except Exception:
        overrides = {}
        redis_status = "unavailable"

    metadata = await dynamic_settings_service.get_metadata()
    updated_at = _parse_updated_at(metadata.get("updated_at")) if metadata else None

    normalized_overrides = _normalize_overrides(overrides, defaults)

    return AdminSettingsResponse(
        defaults=defaults,
        overrides=normalized_overrides,
        effective=effective,
        updated_at=updated_at,
        redis_status=redis_status,
    )

