"""Dynamic settings infrastructure package."""

from .service import DynamicSettingsService, get_dynamic_settings_service

__all__ = [
    "DynamicSettingsService",
    "get_dynamic_settings_service",
]
