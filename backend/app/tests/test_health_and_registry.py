# Lightweight tests that do not require DB/Redis

from fastapi.testclient import TestClient

from app.main import app
from app.infrastructure.tasks.task_registry_decorators import (
    extract_config_id,
    all_queues,
    SchedulerType,
)


def test_health_endpoint_ok():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"
    assert data.get("service") == "backend"


def test_extract_config_id():
    assert extract_config_id("task_123") == 123
    assert extract_config_id("foo") is None
    assert extract_config_id("") is None


def test_all_queues_contains_default():
    queues = all_queues()
    assert "default" in queues


def test_scheduler_type_members():
    assert SchedulerType.CRON.value == "cron"
    assert SchedulerType.DATE.value == "date"
    assert SchedulerType.MANUAL.value == "manual"

