from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from .queue import JobQueue
from .schemas import CreateJobRequest, JobResponse
from .store import JobRecord, JobStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

store = JobStore()
job_queue = JobQueue(store)


@asynccontextmanager
async def lifespan(app: FastAPI):
    job_queue.start()
    yield


app = FastAPI(
    title="Minimal Sous-Chef Reference",
    description="Enqueue jobs, interpolate parameters, async worker, optional webhook callback.",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/jobs", response_model=JobResponse)
async def create_job(body: CreateJobRequest) -> JobResponse:
    rec = store.create(
        recipe_name=body.recipe_name,
        parameter_templates=body.parameter_templates,
        template_context=body.template_context,
        input_records=body.input_records,
        webhook_url=body.webhook_url,
        webhook_secret=body.webhook_secret,
    )
    await job_queue.enqueue(rec.id)
    return _to_response(rec)


@app.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> JobResponse:
    rec = store.get(job_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _to_response(rec)


@app.post("/demo/webhook-echo")
async def demo_webhook_echo(payload: dict) -> dict:
    """Optional target for local testing: set webhook_url to this path on same server."""
    logger.info("Webhook echo received keys=%s", list(payload.keys()))
    return {"ok": True, "received_job_id": payload.get("job_id")}


def _to_response(rec: JobRecord) -> JobResponse:
    return JobResponse(
        id=rec.id,
        recipe_name=rec.recipe_name,
        status=rec.status,  # type: ignore[arg-type]
        rendered_parameters=dict(rec.rendered_parameters),
        result=rec.result,
        error=rec.error,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
        webhook_delivered=rec.webhook_delivered,
        webhook_error=rec.webhook_error,
    )
