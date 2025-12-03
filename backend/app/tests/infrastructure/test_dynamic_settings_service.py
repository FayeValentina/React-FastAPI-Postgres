"""Unit tests for the Redis-backed dynamic settings service."""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Tuple

# Provide minimal environment so Settings can initialise during import.
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("PGADMIN_DEFAULT_EMAIL", "admin@example.com")
os.environ.setdefault("PGADMIN_DEFAULT_PASSWORD", "password123")

from app.core.config import settings
from app.infrastructure.dynamic_settings.service import DynamicSettingsService
from app.infrastructure.redis.keyspace import redis_keys


class FakeRedis:
    """Simple async stub mimicking the subset of RedisBase used by the service."""

    def __init__(
        self,
        initial: Dict[str, Any] | None = None,
        *,
        set_success: bool = True,
        redis_key: str | None = None,
        metadata_key: str | None = None,
    ) -> None:
        self.redis_key = redis_key or redis_keys.app.dynamic_settings()
        self.metadata_key = metadata_key or redis_keys.app.dynamic_settings_metadata()
        self.store: Dict[str, Dict[str, Any]] = {}
        if initial is not None:
            self.store[self.redis_key] = dict(initial)
        self.set_success = set_success
        self.ensure_calls = 0
        self.get_calls: List[str] = []
        self.set_calls: List[Tuple[str, Dict[str, Any]]] = []

    async def ensure_connection(self) -> None:  # pragma: no cover - trivial counter
        self.ensure_calls += 1

    async def get_json(self, key: str) -> Dict[str, Any] | None:
        self.get_calls.append(key)
        return self.store.get(key)

    async def set_json(self, key: str, data: Dict[str, Any]) -> bool:
        self.set_calls.append((key, data))
        if not self.set_success:
            return False
        self.store[key] = dict(data)
        return True


def _run(coro):
    """Helper to execute async service calls inside sync pytest tests."""
    return asyncio.run(coro)


def test_get_all_returns_defaults_when_cache_empty():
    fake = FakeRedis(initial=None)
    service = DynamicSettingsService(fake, settings)

    result = _run(service.get_all())

    assert result == settings.dynamic_settings_defaults()
    assert fake.get_calls == [service.redis_key]


def test_get_all_merges_stored_overrides():
    overrides = {"RAG_TOP_K": 9, "EXTRA_PARAM": "value"}
    fake = FakeRedis(initial=overrides.copy())
    service = DynamicSettingsService(fake, settings)

    result = _run(service.get_all())
    defaults = settings.dynamic_settings_defaults()

    assert result["RAG_TOP_K"] == 9
    assert result["EXTRA_PARAM"] == "value"
    for key, default_value in defaults.items():
        assert result[key] == overrides.get(key, default_value)


def test_update_persists_and_returns_snapshot():
    fake = FakeRedis(initial={"RAG_TOP_K": 10})
    service = DynamicSettingsService(fake, settings)

    async def scenario():
        updated = await service.update({"RAG_TOP_K": 24, "NEW_KEY": "hello"})
        after = await service.get_all()
        return updated, after

    updated, after = _run(scenario())

    assert updated["RAG_TOP_K"] == 24
    assert "NEW_KEY" in updated
    assert after["RAG_TOP_K"] == 24
    assert fake.store[service.redis_key]["RAG_TOP_K"] == 24
    assert fake.store[service.redis_key]["NEW_KEY"] == "hello"
    assert fake.set_calls[0][0] == service.redis_key
    assert fake.set_calls[1][0] == service.metadata_key
    assert "updated_at" in fake.store[service.metadata_key]


def test_update_falls_back_when_redis_write_fails():
    fake = FakeRedis(initial={"RAG_TOP_K": 5}, set_success=False)
    service = DynamicSettingsService(fake, settings)

    result = _run(service.update({"RAG_TOP_K": 42}))

    assert result["RAG_TOP_K"] == 5  # returns previous snapshot
    assert fake.store[service.redis_key]["RAG_TOP_K"] == 5  # persisted value unchanged
    assert fake.set_calls[0][0] == service.redis_key


def test_cached_value_tracks_refresh_and_updates():
    fake = FakeRedis(initial={"RAG_TOP_K": 17})
    service = DynamicSettingsService(fake, settings)

    assert service.cached_value("RAG_TOP_K", None) == settings.RAG_TOP_K

    refreshed = _run(service.get_all())

    assert refreshed["RAG_TOP_K"] == 17
    assert service.cached_value("RAG_TOP_K") == 17

    _run(service.update({"RAG_TOP_K": 33}))

    assert service.cached_value("RAG_TOP_K") == 33
