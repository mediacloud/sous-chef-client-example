from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any
from uuid import uuid4


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class JobRecord:
    id: str
    recipe_name: str
    status: str
    parameter_templates: dict[str, str]
    template_context: dict[str, Any]
    input_records: list[dict[str, Any]]
    webhook_url: str | None
    webhook_secret: str | None
    rendered_parameters: dict[str, str] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)
    webhook_delivered: bool | None = None
    webhook_error: str | None = None


class JobStore:
    """In-memory job registry (reference only — use a DB in production)."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._jobs: dict[str, JobRecord] = {}

    def create(
        self,
        *,
        recipe_name: str,
        parameter_templates: dict[str, str],
        template_context: dict[str, Any],
        input_records: list[dict[str, Any]],
        webhook_url: str | None,
        webhook_secret: str | None,
    ) -> JobRecord:
        jid = str(uuid4())
        rec = JobRecord(
            id=jid,
            recipe_name=recipe_name,
            status="queued",
            parameter_templates=dict(parameter_templates),
            template_context=dict(template_context),
            input_records=list(input_records),
            webhook_url=webhook_url,
            webhook_secret=webhook_secret,
        )
        with self._lock:
            self._jobs[jid] = rec
        return rec

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **kwargs: Any) -> None:
        with self._lock:
            rec = self._jobs.get(job_id)
            if rec is None:
                return
            for k, v in kwargs.items():
                setattr(rec, k, v)
            rec.updated_at = utcnow()
