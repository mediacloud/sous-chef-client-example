"""FastAPI dependencies shared across routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status

from .config import Settings, get_settings


def require_kitchen_settings() -> Settings:
    """503 unless ``KITCHEN_AUTH_EMAIL`` and ``KITCHEN_AUTH_KEY`` are set."""
    s = get_settings()
    if not s.has_kitchen_credentials():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Set KITCHEN_AUTH_EMAIL and KITCHEN_AUTH_KEY (and optionally KITCHEN_BASE_URL).",
        )
    return s


# Use as ``settings: KitchenSettings`` on routes that call Kitchen.
KitchenSettings = Annotated[Settings, Depends(require_kitchen_settings)]
