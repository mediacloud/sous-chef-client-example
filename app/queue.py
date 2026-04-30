from __future__ import annotations

import asyncio
import logging

import httpx

from .processor import do_something_with_data
from .store import JobStore, utcnow
from .templates import render_parameter_templates, replace_named_placeholder
from .schemas import WebhookCallbackPayload

logger = logging.getLogger(__name__)


def _apply_location_placeholder(
    rendered: dict[str, str],
    template_context: dict,
) -> dict[str, str]:
    loc = template_context.get("location_expression")
    if loc is None or loc == "":
        return rendered
    out = dict(rendered)
    for key, val in list(out.items()):
        if "LOCATION_PLACEHOLDER" in val:
            out[key] = replace_named_placeholder(val, "LOCATION_PLACEHOLDER", str(loc))
    return out


class JobQueue:
    def __init__(self, store: JobStore) -> None:
        self._store = store
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._worker_loop(), name="job-worker")

    async def enqueue(self, job_id: str) -> None:
        await self._queue.put(job_id)

    async def _worker_loop(self) -> None:
        while True:
            job_id = await self._queue.get()
            try:
                await self._run_one(job_id)
            except Exception:
                logger.exception("Job %s crashed the worker loop step", job_id)
            finally:
                self._queue.task_done()

    async def _run_one(self, job_id: str) -> None:
        rec = self._store.get(job_id)
        if rec is None:
            return

        self._store.update(job_id, status="running")

        try:
            rendered = render_parameter_templates(rec.parameter_templates, rec.template_context)
            rendered = _apply_location_placeholder(rendered, rec.template_context)
        except Exception as exc:
            self._store.update(job_id, status="failed", error=f"template: {exc}")
            await self._maybe_webhook(job_id)
            return

        self._store.update(job_id, rendered_parameters=rendered)

        try:
            result = do_something_with_data(rec.recipe_name, rendered, rec.input_records)
        except Exception as exc:
            self._store.update(job_id, status="failed", error=f"process: {exc}")
            await self._maybe_webhook(job_id)
            return

        # Keep status as "running" until the webhook attempt finishes so clients that poll
        # `GET /jobs/{id}` do not see "completed" while `webhook_delivered` is still null
        # (httpx suspends the worker and other requests can interleave).
        self._store.update(job_id, result=result)
        await self._maybe_webhook(job_id)
        self._store.update(job_id, status="completed")

    async def _maybe_webhook(self, job_id: str) -> None:
        rec = self._store.get(job_id)
        if rec is None or not rec.webhook_url:
            return

        notif_status = "failed" if rec.error else ("completed" if rec.result is not None else rec.status)
        payload = WebhookCallbackPayload(
            job_id=rec.id,
            recipe_name=rec.recipe_name,
            status=notif_status,
            rendered_parameters=dict(rec.rendered_parameters),
            result=rec.result,
            error=rec.error,
            completed_at=utcnow(),
        )
        headers = {}
        if rec.webhook_secret:
            headers["X-Webhook-Secret"] = rec.webhook_secret

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    rec.webhook_url,
                    json=payload.model_dump(mode="json"),
                    headers=headers,
                )
                r.raise_for_status()
            self._store.update(job_id, webhook_delivered=True, webhook_error=None)
        except Exception as exc:
            self._store.update(
                job_id,
                webhook_delivered=False,
                webhook_error=str(exc)[:500],
            )
