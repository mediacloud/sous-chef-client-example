from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class CreateJobRequest(BaseModel):
    """Submit a job: recipe name, parameter templates + context, optional sample data to process."""

    recipe_name: str = Field(..., examples=["tagged_filtered_summaries"])
    parameter_templates: dict[str, str] = Field(
        default_factory=dict,
        description='String templates using {placeholders}, e.g. query: \'({location}) AND "topic"~1000\'',
    )
    template_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Values substituted into parameter_templates (also supports nested keys via dot paths).",
    )
    input_records: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Toy rows passed to the processor (e.g. CSV-shaped dicts).",
    )
    webhook_url: str | None = Field(
        default=None,
        description="If set, POST job completion JSON here when the worker finishes.",
    )
    webhook_secret: str | None = None


class JobResponse(BaseModel):
    id: str
    recipe_name: str
    status: Literal["queued", "running", "completed", "failed"]
    rendered_parameters: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    webhook_delivered: bool | None = None
    webhook_error: str | None = None


class WebhookCallbackPayload(BaseModel):
    """Simpler than production Kitchen webhooks; enough to show the callback pattern."""

    job_id: str
    recipe_name: str
    status: str
    rendered_parameters: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None
    completed_at: datetime
