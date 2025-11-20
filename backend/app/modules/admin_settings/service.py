from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal

from fastapi import HTTPException, status

from app.infrastructure.dynamic_settings import DynamicSettingsService
from .schemas import AdminSettingsResponse, AdminSettingsUpdate


class AdminSettingsService:
    """Business logic for managing dynamic administrator settings."""

    @staticmethod
    def _normalize_overrides(
        overrides: Dict[str, Any], defaults: Dict[str, Any]
    ) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}
        for key, value in overrides.items():
            if key in defaults and defaults[key] == value:
                continue
            normalized[key] = value
        return normalized

    @staticmethod
    def _parse_updated_at(raw: Any) -> datetime | None:
        if isinstance(raw, datetime):
            return raw
        if isinstance(raw, str):
            try:
                return datetime.fromisoformat(raw)
            except ValueError:
                return None
        return None

    async def read_settings(
        self, dynamic_settings_service: DynamicSettingsService
    ) -> AdminSettingsResponse:
        defaults = dynamic_settings_service.defaults()
        effective = await dynamic_settings_service.get_all()

        redis_status: Literal["ok", "unavailable"] = "ok"
        overrides = await dynamic_settings_service.get_overrides()

        metadata = await dynamic_settings_service.get_metadata()
        updated_at = (
            self._parse_updated_at(metadata.get("updated_at")) if metadata else None
        )

        normalized_overrides = self._normalize_overrides(overrides, defaults)

        return AdminSettingsResponse(
            defaults=defaults,
            overrides=normalized_overrides,
            effective=effective,
            updated_at=updated_at,
            redis_status=redis_status,
        )

    async def update_settings(
        self,
        payload: AdminSettingsUpdate,
        dynamic_settings_service: DynamicSettingsService,
    ) -> AdminSettingsResponse:
        updates = payload.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No settings provided",
            )

        await dynamic_settings_service.update(updates)
        return await self.read_settings(dynamic_settings_service)

    async def reset_settings(
        self,
        dynamic_settings_service: DynamicSettingsService,
        keys: list[str] | None = None,
    ) -> AdminSettingsResponse:
        try:
            if keys:
                await dynamic_settings_service.reset(keys)
            else:
                await dynamic_settings_service.reset()
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        return await self.read_settings(dynamic_settings_service)


admin_settings_service = AdminSettingsService()
