from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_queue_drains_to_completed_with_mock_kitchen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KITCHEN_AUTH_EMAIL", "test@example.com")
    monkeypatch.setenv("KITCHEN_AUTH_KEY", "fake-key")
    get_settings.cache_clear()

    def fake_start(s, recipe_name: str, params: dict) -> dict:
        return {"mock_run_id": "r1", "recipe_name": recipe_name}

    monkeypatch.setattr("app.run_queue.kitchen_start_recipe", fake_start)

    with TestClient(app) as client:
        r = client.post(
            "/api/queue/runs",
            json={"recipe_name": "demo_recipe", "recipe_parameters": {"a": 1}},
        )
        assert r.status_code == 200
        jid = r.json()["id"]
        assert r.json()["status"] in ("queued", "running", "completed")

        final = None
        for _ in range(100):
            g = client.get(f"/api/queue/jobs/{jid}")
            assert g.status_code == 200
            final = g.json()
            if final["status"] in ("completed", "failed"):
                break
            time.sleep(0.02)
        else:
            pytest.fail(f"queue job did not finish: {final}")

        assert final["status"] == "completed"
        assert final["kitchen_response"] == {"mock_run_id": "r1", "recipe_name": "demo_recipe"}

    monkeypatch.delenv("KITCHEN_AUTH_EMAIL", raising=False)
    monkeypatch.delenv("KITCHEN_AUTH_KEY", raising=False)
    get_settings.cache_clear()


def test_queue_job_unknown_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KITCHEN_AUTH_EMAIL", "test@example.com")
    monkeypatch.setenv("KITCHEN_AUTH_KEY", "fake-key")
    get_settings.cache_clear()

    with TestClient(app) as client:
        r = client.get("/api/queue/jobs/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    monkeypatch.delenv("KITCHEN_AUTH_EMAIL", raising=False)
    monkeypatch.delenv("KITCHEN_AUTH_KEY", raising=False)
    get_settings.cache_clear()
