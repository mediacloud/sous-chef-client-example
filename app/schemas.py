from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class RecipeStartRequest(BaseModel):
    """Body for ``POST /api/runs`` → Kitchen ``recipe/start``."""

    recipe_name: str
    recipe_parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Passed as JSON to Kitchen (include webhook_url / webhook_secret here when starting flows).",
    )


class QueuedRunResponse(BaseModel):
    """Status of a ``POST /api/queue/runs`` job (processed by the in-process worker)."""

    id: str
    recipe_name: str
    status: Literal["queued", "running", "completed", "failed"]
    kitchen_response: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
