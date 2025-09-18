from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import os
import sys
import types

os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("PGADMIN_DEFAULT_EMAIL", "admin@example.com")
os.environ.setdefault("PGADMIN_DEFAULT_PASSWORD", "password123")

if "sentence_transformers" not in sys.modules:
    fake_sentence_transformers = types.ModuleType("sentence_transformers")

    class _DummySentenceTransformer:  # pragma: no cover - simple stub
        def __init__(self, *args, **kwargs) -> None:
            pass

        def encode(self, texts, normalize_embeddings=True):
            return []

    fake_sentence_transformers.SentenceTransformer = _DummySentenceTransformer
    sys.modules["sentence_transformers"] = fake_sentence_transformers

from app.api.v1.endpoints import admin_settings
from app.core.config import settings
from app.infrastructure.dynamic_settings import get_dynamic_settings_service


class FakeDynamicSettingsService:
    def __init__(self) -> None:
        self._defaults = settings.dynamic_settings_defaults()
        self._overrides: Dict[str, Any] = {}
        self._updated_at: datetime | None = None

    def defaults(self) -> Dict[str, Any]:
        return dict(self._defaults)

    async def get_all(self) -> Dict[str, Any]:
        merged = dict(self._defaults)
        merged.update(self._overrides)
        return merged

    async def get_overrides(self) -> Dict[str, Any]:
        return dict(self._overrides)

    async def get_metadata(self) -> Dict[str, Any]:
        if self._updated_at is None:
            return {}
        return {"updated_at": self._updated_at.isoformat()}

    async def update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self._overrides.update(payload)
        self._updated_at = datetime.now(timezone.utc)
        merged = dict(self._defaults)
        merged.update(self._overrides)
        return merged


@pytest.fixture()
def admin_client() -> tuple[TestClient, FakeDynamicSettingsService, str]:
    test_app = FastAPI()
    test_app.include_router(admin_settings.router, prefix="/api/v1")

    client = TestClient(test_app)
    fake_service = FakeDynamicSettingsService()

    test_app.dependency_overrides[get_dynamic_settings_service] = lambda: fake_service

    original_secret = settings.INTERNAL_API_SECRET
    settings.INTERNAL_API_SECRET = "test-internal-secret"

    try:
        yield client, fake_service, "test-internal-secret"
    finally:
        settings.INTERNAL_API_SECRET = original_secret
        test_app.dependency_overrides.clear()


def test_admin_settings_requires_internal_secret(admin_client: tuple[TestClient, FakeDynamicSettingsService, str]):
    client, _, _ = admin_client

    response = client.get("/api/v1/admin/settings")

    assert response.status_code == 403


def test_admin_settings_get_returns_defaults(admin_client: tuple[TestClient, FakeDynamicSettingsService, str]):
    client, _, secret = admin_client

    response = client.get(
        "/api/v1/admin/settings",
        headers={"X-Internal-Secret": secret},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["redis_status"] == "ok"
    assert data["overrides"] == {}
    assert data["defaults"]["RAG_TOP_K"] == settings.RAG_TOP_K
    assert data["effective"]["RAG_TOP_K"] == settings.RAG_TOP_K
    assert data["updated_at"] is None


def test_admin_settings_update_overrides_values(admin_client: tuple[TestClient, FakeDynamicSettingsService, str]):
    client, _, secret = admin_client

    response = client.put(
        "/api/v1/admin/settings",
        json={"RAG_TOP_K": 7, "RAG_MIN_SIM": 0.55},
        headers={"X-Internal-Secret": secret},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["overrides"]["RAG_TOP_K"] == 7
    assert data["effective"]["RAG_TOP_K"] == 7
    assert data["effective"]["RAG_MIN_SIM"] == pytest.approx(0.55)
    assert data["redis_status"] == "ok"
    assert data["updated_at"] is not None
