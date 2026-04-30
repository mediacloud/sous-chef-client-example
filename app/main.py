from __future__ import annotations

import json
import logging
import tempfile
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Header, Query, status

from .config import Settings, get_settings
from .deps import KitchenSettings
from .kitchen_service import (
    fetch_run,
    fetch_run_artifacts,
    list_recipes,
    recipe_schema,
    start_recipe,
    validate_auth,
)
from .run_queue import QueuedRunJob, run_queue
from .schemas import QueuedRunResponse, RecipeStartRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _queued_run_response(job: QueuedRunJob) -> QueuedRunResponse:
    return QueuedRunResponse(
        id=job.id,
        recipe_name=job.recipe_name,
        status=job.status,
        kitchen_response=job.kitchen_response,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _call_kitchen(operation: str, settings: Settings, fn: Callable[[Settings], Any]) -> Any:
    """Run a blocking Kitchen client call; map failures to HTTP 502."""
    try:
        return fn(settings)
    except Exception as exc:
        logger.exception("%s failed", operation)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc)[:800],
        ) from exc


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_queue.start()
    yield


app = FastAPI(
    title="Minimal Sous-Chef Kitchen client reference",
    description=(
        "HTTP facade over sous-chef-kitchen-client: list recipes, start runs, fetch status and artifacts. "
        "Optional serial queue (POST /api/queue/runs) demonstrates deferred Kitchen submissions. "
        "Build recipe_parameters with helpers in app.maps_queries."
    ),
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config")
def public_config() -> dict[str, object]:
    """Local configuration only; does not call Kitchen."""
    s = get_settings()
    return {
        "kitchen_base_url": s.kitchen_base_url,
        "credentials_configured": s.has_kitchen_credentials(),
        "webhook_path": s.webhook_path,
        "webhook_secret_configured": s.webhook_auth_configured(),
        "public_app_url": s.public_app_url or None,
        "suggested_webhook_url": s.suggested_webhook_url(),
    }


@app.get("/api/auth/validate")
def api_validate_auth(settings: KitchenSettings) -> dict[str, object]:
    """Kitchen ``GET auth/validate``."""
    return _call_kitchen(
        "Kitchen validate_auth",
        settings,
        lambda s: validate_auth(s).model_dump(mode="json"),
    )


@app.get("/api/recipes")
def api_recipes(settings: KitchenSettings) -> dict[str, object]:
    """Kitchen ``GET recipe/list``."""
    return _call_kitchen("Kitchen recipe_list", settings, list_recipes)


@app.get("/api/recipes/schema")
def api_recipe_schema(
    settings: KitchenSettings,
    recipe_name: str = Query(..., description="Flow name registered in Kitchen"),
) -> dict[str, object]:
    """Kitchen ``GET recipe/schema``."""
    return _call_kitchen(
        "Kitchen recipe_schema",
        settings,
        lambda s: recipe_schema(s, recipe_name),
    )


@app.post("/api/queue/runs", response_model=QueuedRunResponse)
async def api_queue_run(body: RecipeStartRequest, _settings: KitchenSettings) -> QueuedRunResponse:
    """
    Enqueue a Kitchen ``start_recipe`` call; a background worker processes one job at a time.

    Same body as ``POST /api/runs``; returns immediately with ``status=queued`` while work is pending.
    """
    job = await run_queue.submit(body.recipe_name, dict(body.recipe_parameters))
    return _queued_run_response(job)


@app.get("/api/queue/jobs/{job_id}", response_model=QueuedRunResponse)
def api_queue_job(job_id: str, _settings: KitchenSettings) -> QueuedRunResponse:
    """Poll queued job status (``queued`` → ``running`` → ``completed`` or ``failed``)."""
    job = run_queue.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown queue job id")
    return _queued_run_response(job)


@app.post("/api/runs")
def api_start_run(body: RecipeStartRequest, settings: KitchenSettings) -> dict[str, object]:
    """Kitchen ``POST recipe/start``."""
    return _call_kitchen(
        "Kitchen start_recipe",
        settings,
        lambda s: start_recipe(s, body.recipe_name, dict(body.recipe_parameters)),
    )


@app.get("/api/runs/{run_id}")
def api_get_run(run_id: str, settings: KitchenSettings) -> dict[str, object]:
    """Kitchen ``GET run/{run_id}``."""
    return _call_kitchen(
        "Kitchen fetch_run_by_id",
        settings,
        lambda s: fetch_run(s, run_id),
    )


@app.get("/api/runs/{run_id}/artifacts")
def api_get_run_artifacts(run_id: str, settings: KitchenSettings) -> dict[str, object]:
    """Kitchen ``GET run/{run_id}/artifacts``."""
    return _call_kitchen(
        "Kitchen fetch_run_artifacts",
        settings,
        lambda s: fetch_run_artifacts(s, run_id),
    )


@app.post("/webhooks/sous-chef")
def sous_chef_webhook(
    payload: dict[str, Any],
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
) -> dict[str, object]:
    """
    Minimal Kitchen completion webhook: log a line and persist the JSON body to a temp file.

    Set ``WEBHOOK_SECRET`` in the environment to require the same value in ``X-Webhook-Secret``.
    Point ``webhook_url`` in ``POST /api/runs`` to your public base + ``/webhooks/sous-chef`` (see ``GET /api/config``).
    """
    s = get_settings()
    expected = (s.webhook_secret or "").strip()
    if expected and (x_webhook_secret or "").strip() != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook secret")

    run_id = None
    run = payload.get("run")
    if isinstance(run, dict):
        run_id = run.get("id")

    logger.info(
        "Sous-Chef webhook: kitchen_run_id=%s recipe=%s",
        run_id,
        (run or {}).get("recipe_name") if isinstance(run, dict) else None,
    )

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix="sous-chef-webhook-",
        suffix=".json",
        delete=False,
    ) as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2, default=str)
        path = tmp.name

    return {
        "ok": True,
        "saved_path": path,
        "kitchen_run_id": str(run_id) if run_id is not None else None,
    }
