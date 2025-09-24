from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_superuser
from app.infrastructure.dynamic_settings import (
    DynamicSettingsService,
    get_dynamic_settings_service,
)
from app.modules.admin_settings.schemas import (
    AdminSettingsResponse,
    AdminSettingsUpdate,
    AdminSettingsResetRequest,
)
from app.modules.admin_settings.service import admin_settings_service


router = APIRouter(
    prefix="/admin/settings",
    tags=["admin-settings"],
    dependencies=[Depends(get_current_superuser)],
)


@router.get("/", response_model=AdminSettingsResponse)
async def read_admin_settings(
    dynamic_settings_service: DynamicSettingsService = Depends(get_dynamic_settings_service),
) -> AdminSettingsResponse:
    return await admin_settings_service.read_settings(dynamic_settings_service)


@router.put("/", response_model=AdminSettingsResponse)
async def update_admin_settings(
    payload: AdminSettingsUpdate,
    dynamic_settings_service: DynamicSettingsService = Depends(get_dynamic_settings_service),
) -> AdminSettingsResponse:
    return await admin_settings_service.update_settings(payload, dynamic_settings_service)


@router.post("/reset", response_model=AdminSettingsResponse)
async def reset_admin_settings(
    payload: AdminSettingsResetRequest,
    dynamic_settings_service: DynamicSettingsService = Depends(get_dynamic_settings_service),
) -> AdminSettingsResponse:
    return await admin_settings_service.reset_settings(dynamic_settings_service, payload.keys)
