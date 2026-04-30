"""
Very thin in-memory queue: enqueue Kitchen ``start_recipe`` work and process it **serially**
in a single asyncio worker.

**Ordering:** The worker handles **one job at a time**. It awaits each ``kitchen_start_recipe``
call (HTTP ``start_recipe`` to Kitchen) before starting the next queued job. That serializes
**submissions** to Kitchen when multiple clients hit ``POST /api/queue/runs``.

**What “done” means:** A queue job reaches ``completed`` when Kitchen’s ``start_recipe`` returns
successfully (or ``failed`` if it raises). This does **not** mean the remote Sous-Chef recipe has
finished processing—usually Kitchen accepts the run and returns metadata quickly while work
continues asynchronously. Only if the client API blocked until the run finished would the queue
implicitly wait for that.

Demonstrates the same *shape* as a larger app’s Kitchen submission queue without persistence.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from .config import get_settings
from .kitchen_service import start_recipe as kitchen_start_recipe

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class QueuedRunJob:
    id: str
    recipe_name: str
    recipe_parameters: dict[str, Any]
    status: Literal["queued", "running", "completed", "failed"] = "queued"
    kitchen_response: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)


class RunQueue:
    """
    Single-worker asyncio queue over Kitchen ``start_recipe`` calls.

    ``threading.Lock`` protects ``_jobs`` because sync route handlers read status while the
    asyncio worker updates the same dict from another task.
    """

    def __init__(self) -> None:
        # Queue is created in ``start()`` on the active event loop (``asyncio.Queue`` is loop-bound).
        self._queue: asyncio.Queue[str] | None = None
        self._jobs: dict[str, QueuedRunJob] = {}
        self._lock = threading.Lock()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        # Re-create queue + worker after app shutdown (e.g. each TestClient) or when the old task finished.
        if self._task is not None and not self._task.done():
            return
        self._queue = asyncio.Queue()
        self._task = asyncio.create_task(self._worker_loop(), name="kitchen-run-queue")

    async def submit(self, recipe_name: str, recipe_parameters: dict[str, Any]) -> QueuedRunJob:
        if self._queue is None:
            raise RuntimeError("RunQueue.start() was not called")
        job_id = str(uuid4())
        job = QueuedRunJob(
            id=job_id,
            recipe_name=recipe_name,
            recipe_parameters=dict(recipe_parameters),
        )
        with self._lock:
            self._jobs[job_id] = job
        await self._queue.put(job_id)
        return job

    def get(self, job_id: str) -> QueuedRunJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _update(self, job_id: str, **kwargs: Any) -> None:
        with self._lock:
            rec = self._jobs.get(job_id)
            if rec is None:
                return
            for k, v in kwargs.items():
                setattr(rec, k, v)
            rec.updated_at = _utcnow()

    async def _worker_loop(self) -> None:
        assert self._queue is not None
        while True:
            job_id = await self._queue.get()
            try:
                await self._run_one(job_id)
            except Exception:
                logger.exception("Queue worker failed for job_id=%s", job_id)
            finally:
                self._queue.task_done()

    async def _run_one(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            return

        self._update(job_id, status="running")
        s = get_settings()
        try:
            result = await asyncio.to_thread(
                kitchen_start_recipe,
                s,
                job.recipe_name,
                job.recipe_parameters,
            )
        except Exception as exc:
            logger.exception("Queued start_recipe failed job_id=%s", job_id)
            self._update(job_id, status="failed", error=str(exc)[:2000], kitchen_response=None)
            return

        self._update(
            job_id,
            status="completed",
            kitchen_response=result if isinstance(result, dict) else {"raw": result},
        )


run_queue = RunQueue()
