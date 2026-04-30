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

    def has_kitchen_credentials(self) -> bool:
        return bool(self.kitchen_auth_email.strip() and self.kitchen_auth_key.strip())

    def webhook_auth_configured(self) -> bool:
        return bool(self.webhook_secret.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
