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
    monkeypatch.delenv("PUBLIC_APP_URL", raising=False)
    get_settings.cache_clear()

    with TestClient(app) as client:
        r = client.get("/api/config")
        assert r.status_code == 200
        data = r.json()
        assert data["credentials_configured"] is False
        assert data["public_app_url"] is None
        assert data["suggested_webhook_url"] is None


def test_api_config_suggested_webhook_url_with_public_app_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KITCHEN_AUTH_EMAIL", raising=False)
    monkeypatch.delenv("KITCHEN_AUTH_KEY", raising=False)
    monkeypatch.setenv("PUBLIC_APP_URL", "https://example.ngrok-free.app")
    monkeypatch.setenv("WEBHOOK_PATH", "/webhooks/sous-chef")
    get_settings.cache_clear()

    with TestClient(app) as client:
        r = client.get("/api/config")
        assert r.status_code == 200
        data = r.json()
        assert data["public_app_url"] == "https://example.ngrok-free.app"
        assert data["suggested_webhook_url"] == "https://example.ngrok-free.app/webhooks/sous-chef"


def test_api_recipes_503_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KITCHEN_AUTH_EMAIL", raising=False)
    monkeypatch.delenv("KITCHEN_AUTH_KEY", raising=False)
    get_settings.cache_clear()

    with TestClient(app) as client:
        r = client.get("/api/recipes")
        assert r.status_code == 503
