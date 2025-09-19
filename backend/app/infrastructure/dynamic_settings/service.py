"""Service layer for dynamic, Redis-backed application settings."""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict

from app.core.config import Settings, settings
from app.infrastructure.redis.keyspace import redis_keys
from app.infrastructure.redis.redis_base import RedisBase

logger = logging.getLogger(__name__)


class DynamicSettingsService:
    """Load and persist dynamic settings stored in Redis with safe fallbacks."""

    def __init__(
        self,
        redis_client: RedisBase,
        settings: Settings,
        redis_key: str | None = None,
        meta_key: str | None = None,
    ):
        self._redis = redis_client
        self._settings = settings
        self._redis_key = redis_key or redis_keys.app.dynamic_settings()
        self._meta_key = meta_key or redis_keys.app.dynamic_settings_metadata()
        self._latest_lock = threading.RLock()
        self._latest_effective: Dict[str, Any] = self.defaults()

    @property
    def redis_key(self) -> str:
        return self._redis_key

    @property
    def metadata_key(self) -> str:
        return self._meta_key

    def defaults(self) -> dict[str, Any]:
        """Return a fresh copy of default dynamic settings."""
        return dict(self._settings.dynamic_settings_defaults())

    def _set_latest_effective(self, snapshot: Dict[str, Any]) -> None:
        with self._latest_lock:
            self._latest_effective = dict(snapshot)

    def cached_effective(self) -> Dict[str, Any]:
        """Return the most recently observed effective settings snapshot."""
        with self._latest_lock:
            return dict(self._latest_effective)

    def cached_value(self, key: str, default: Any | None = None) -> Any:
        """Return a setting from the cached snapshot, falling back to default."""
        with self._latest_lock:
            return self._latest_effective.get(key, default)

    async def get_all(self) -> dict[str, Any]:
        """Return merged dynamic settings with Redis overrides when available."""
        defaults = self.defaults()
        try:
            await self._redis.ensure_connection()
            payload = await self._redis.get_json(self._redis_key)
        except Exception as exc:  # pragma: no cover - defensive, RedisBase already logs
            if isinstance(exc, asyncio.CancelledError):
                raise
            logger.warning("Falling back to default dynamic settings due to Redis error: %s", exc)
            self._set_latest_effective(defaults)
            return defaults

        if not payload:
            self._set_latest_effective(defaults)
            return defaults

        if not isinstance(payload, dict):
            logger.warning(
                "Dynamic settings payload for key %s is not a JSON object, ignoring", self._redis_key
            )
            self._set_latest_effective(defaults)
            return defaults

        merged: Dict[str, Any] = dict(defaults)
        merged.update(payload)
        self._set_latest_effective(merged)
        return merged

    async def get_overrides(self) -> dict[str, Any]:
        """Return raw overrides persisted in Redis without merging defaults."""
        try:
            await self._redis.ensure_connection()
            payload = await self._redis.get_json(self._redis_key)
        except Exception as exc:  # pragma: no cover - defensive
            if isinstance(exc, asyncio.CancelledError):
                raise
            logger.warning("Failed to load dynamic settings overrides: %s", exc)
            raise

        if not payload:
            return {}
        if not isinstance(payload, dict):
            logger.warning(
                "Dynamic settings overrides payload for key %s is not a JSON object, ignoring",
                self._redis_key,
            )
            return {}
        return dict(payload)

    async def get_metadata(self) -> dict[str, Any]:
        """Return metadata such as updated timestamps for dynamic settings."""
        try:
            await self._redis.ensure_connection()
            payload = await self._redis.get_json(self._meta_key)
        except Exception as exc:  # pragma: no cover - defensive
            if isinstance(exc, asyncio.CancelledError):
                raise
            logger.warning("Failed to load dynamic settings metadata: %s", exc)
            return {}

        if not payload or not isinstance(payload, dict):
            return {}
        return dict(payload)

    async def update(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Persist patched dynamic settings and return the merged document."""
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dictionary of settings overrides")

        current = await self.get_all()
        merged: Dict[str, Any] = dict(current)
        merged.update(payload)

        try:
            await self._redis.ensure_connection()
            persisted = await self._redis.set_json(self._redis_key, merged)
        except Exception as exc:  # pragma: no cover - defensive, RedisBase already logs
            if isinstance(exc, asyncio.CancelledError):
                raise
            logger.error("Failed to persist dynamic settings to Redis: %s", exc)
            return current

        if not persisted:
            logger.error("Redis rejected dynamic settings write for key %s", self._redis_key)
            return current

        timestamp = datetime.now(timezone.utc).isoformat()
        metadata = {
            "updated_at": timestamp,
            "updated_fields": sorted(payload.keys()),
        }
        self._set_latest_effective(merged)
        try:
            meta_persisted = await self._redis.set_json(self._meta_key, metadata)
            if not meta_persisted:
                logger.warning("Redis rejected dynamic settings metadata write for key %s", self._meta_key)
        except Exception as exc:  # pragma: no cover - defensive
            if isinstance(exc, asyncio.CancelledError):
                raise
            logger.warning("Failed to persist dynamic settings metadata: %s", exc)

        return dict(merged)

    async def refresh(self) -> dict[str, Any]:
        """Refresh the cached snapshot from Redis and return the latest values."""
        return await self.get_all()


@lru_cache(maxsize=1)
def _build_dynamic_settings_service() -> DynamicSettingsService:
    """Return a singleton DynamicSettingsService bound to the shared Redis pool."""
    return DynamicSettingsService(RedisBase(), settings)


def get_dynamic_settings_service() -> DynamicSettingsService:
    """FastAPI dependency hook for retrieving the shared DynamicSettingsService."""
    return _build_dynamic_settings_service()
