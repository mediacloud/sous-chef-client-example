from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    kitchen_base_url: str = "https://kitchen-staging.tarbell.mediacloud.org"
    kitchen_auth_email: str = ""
    kitchen_auth_key: str = ""

    # Optional: if set, ``POST /webhooks/sous-chef`` requires matching ``X-Webhook-Secret`` header.
    webhook_secret: str = ""
    webhook_path: str = "/webhooks/sous-chef"

    # Public HTTPS base for this app (no trailing slash), e.g. ngrok ``https://abc.ngrok-free.app``.
    # Used with ``webhook_path`` to build ``suggested_webhook_url`` for ``GET /api/config``.
    public_app_url: str = ""

    def has_kitchen_credentials(self) -> bool:
        return bool(self.kitchen_auth_email.strip() and self.kitchen_auth_key.strip())

    def webhook_auth_configured(self) -> bool:
        return bool(self.webhook_secret.strip())

    def suggested_webhook_url(self) -> str | None:
        """Full URL for ``recipe_parameters["webhook_url"]`` when Kitchen posts completion payloads."""
        base = (self.public_app_url or "").strip().rstrip("/")
        if not base:
            return None
        path = (self.webhook_path or "/webhooks/sous-chef").strip()
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{base}{path}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
