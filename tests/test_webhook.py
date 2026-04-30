from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_webhook_saves_payload_and_returns_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("WEBHOOK_SECRET", raising=False)
    get_settings.cache_clear()

    with TestClient(app) as client:
        body = {"run": {"id": "kitchen-1", "recipe_name": "full_text_download", "status": "completed"}}
        r = client.post("/webhooks/sous-chef", json=body)
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["kitchen_run_id"] == "kitchen-1"
        saved = Path(data["saved_path"])
        assert saved.is_file()
        assert json.loads(saved.read_text(encoding="utf-8")) == body
        saved.unlink(missing_ok=True)


def test_webhook_rejects_bad_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBHOOK_SECRET", "expected-secret")
    get_settings.cache_clear()

    with TestClient(app) as client:
        r = client.post("/webhooks/sous-chef", json={}, headers={"X-Webhook-Secret": "wrong"})
        assert r.status_code == 403

    monkeypatch.delenv("WEBHOOK_SECRET", raising=False)
    get_settings.cache_clear()
