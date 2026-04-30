from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_api_config_reports_credentials_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KITCHEN_AUTH_EMAIL", raising=False)
    monkeypatch.delenv("KITCHEN_AUTH_KEY", raising=False)
    get_settings.cache_clear()

    with TestClient(app) as client:
        r = client.get("/api/config")
        assert r.status_code == 200
        assert r.json()["credentials_configured"] is False


def test_api_recipes_503_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KITCHEN_AUTH_EMAIL", raising=False)
    monkeypatch.delenv("KITCHEN_AUTH_KEY", raising=False)
    get_settings.cache_clear()

    with TestClient(app) as client:
        r = client.get("/api/recipes")
        assert r.status_code == 503
