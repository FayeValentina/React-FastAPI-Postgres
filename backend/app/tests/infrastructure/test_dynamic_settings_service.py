"""Unit tests for the Redis-backed dynamic settings service."""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Tuple

import pytest

# Provide minimal environment so Settings can initialise during import.
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("PGADMIN_DEFAULT_EMAIL", "admin@example.com")
os.environ.setdefault("PGADMIN_DEFAULT_PASSWORD", "password123")

from app.core.config import settings
from app.infrastructure.dynamic_settings.service import (
    DYNAMIC_SETTINGS_KEY,
    DYNAMIC_SETTINGS_META_KEY,
    DynamicSettingsService,
)


class FakeRedis:
    """Simple async stub mimicking the subset of RedisBase used by the service."""

    def __init__(
        self,
        initial: Dict[str, Any] | None = None,
        *,
        set_success: bool = True,
    ) -> None:
        self.store: Dict[str, Dict[str, Any]] = {}
        if initial is not None:
            self.store[DYNAMIC_SETTINGS_KEY] = dict(initial)
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
    assert fake.get_calls == [DYNAMIC_SETTINGS_KEY]


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
    fake = FakeRedis(initial={"RAG_MIN_SIM": 0.25})
    service = DynamicSettingsService(fake, settings)

    async def scenario():
        updated = await service.update({"RAG_MIN_SIM": 0.9, "NEW_KEY": "hello"})
        after = await service.get_all()
        return updated, after

    updated, after = _run(scenario())

    assert pytest.approx(0.9) == updated["RAG_MIN_SIM"]
    assert "NEW_KEY" in updated
    assert after["RAG_MIN_SIM"] == pytest.approx(0.9)
    assert fake.store[DYNAMIC_SETTINGS_KEY]["RAG_MIN_SIM"] == pytest.approx(0.9)
    assert fake.store[DYNAMIC_SETTINGS_KEY]["NEW_KEY"] == "hello"
    assert fake.set_calls[0][0] == DYNAMIC_SETTINGS_KEY
    assert fake.set_calls[1][0] == DYNAMIC_SETTINGS_META_KEY
    assert "updated_at" in fake.store[DYNAMIC_SETTINGS_META_KEY]


def test_update_falls_back_when_redis_write_fails():
    fake = FakeRedis(initial={"RAG_TOP_K": 5}, set_success=False)
    service = DynamicSettingsService(fake, settings)

    result = _run(service.update({"RAG_TOP_K": 42}))

    assert result["RAG_TOP_K"] == 5  # returns previous snapshot
    assert fake.store[DYNAMIC_SETTINGS_KEY]["RAG_TOP_K"] == 5  # persisted value unchanged
    assert fake.set_calls[0][0] == DYNAMIC_SETTINGS_KEY
