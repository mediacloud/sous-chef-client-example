# Minimal Sous-Chef Kitchen client reference

Self-contained FastAPI app: almost every route delegates to **`sous-chef-kitchen-client`** (`SousChefKitchenAPIClient`). **`POST /api/queue/runs`** adds a tiny serial queue demo on top of ``start_recipe`` (optional pattern). Use this repo to see how to call Kitchen from Python and how to build MediaCloud-oriented **`recipe_parameters`** (query strings, collection ids, etc.) for maps-style flows.

**Library helpers (not HTTP):**

- `app/maps_queries.py` — `HEALTH_STATE_QUERY_TEMPLATE`, `HEALTH_STATE_COLLECTION_ID`, `TAGGED_FILTERED_SUMMARIES_RECIPE` (`"tagged_filtered_summaries"`), Nigeria state/LGA → full `query` string.
- `app/templates.py` — string interpolation (`LOCATION_PLACEHOLDER`, `{labels}`, …) when assembling JSON for `POST /api/runs`.

There is **no** database: the queue keeps jobs **in memory** only. **`POST /webhooks/sous-chef`** is a minimal receiver (log + temp JSON file). When credentials are set, Kitchen calls are real except where you mock them in tests.

## Run

Install requires **git** (the client package is installed from GitHub unless you pre-install it locally).

```bash
cd minimal-sous-chef-reference
python -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8010
```

Pin `sous-chef-kitchen-client` to a tag in `pyproject.toml` instead of `@main` when you need reproducible installs.

## Environment

| Variable | Purpose |
|----------|---------|
| `KITCHEN_BASE_URL` | Kitchen API base (default in `app/config.py`) |
| `KITCHEN_AUTH_EMAIL` | `mediacloud-email` header |
| `KITCHEN_AUTH_KEY` | Bearer token |

If email/key are missing, every route that talks to Kitchen returns **503** with a short explanation. `GET /api/config` only reads local settings (no network).

## HTTP API

| Method | Path | Role |
|--------|------|------|
| GET | `/health` | — |
| GET | `/api/config` | Local env summary |
| GET | `/api/auth/validate` | `validate_auth()` |
| GET | `/api/recipes` | `recipe_list()` |
| GET | `/api/recipes/schema?recipe_name=` | `recipe_schema()` |
| POST | `/api/runs` | `start_recipe()` immediately |
| POST | `/api/queue/runs` | Enqueue same body; background worker calls `start_recipe()` **serially** |
| GET | `/api/queue/jobs/{job_id}` | Poll `queued` → `running` → `completed` / `failed` |
| GET | `/api/runs/{run_id}` | `fetch_run_by_id()` |
| GET | `/api/runs/{run_id}/artifacts` | `fetch_run_artifacts()` |
| POST | `/webhooks/sous-chef` | Receive completion webhook (log + tempfile JSON) |

Pass **`webhook_url`** / **`webhook_secret`** inside **`recipe_parameters`** when starting a flow that posts completion payloads to your service (same idea as production integrations).

### Webhook receiver (local demo)

| Method | Path | Purpose |
|--------|------|--------|
| POST | `/webhooks/sous-chef` | Logs one line and writes the JSON body to a **temp file** (returns `saved_path`). |

Optional env **`WEBHOOK_SECRET`**: when set, requests must send the same value as header **`X-Webhook-Secret`** or the handler returns 403.

`GET /api/config` includes **`webhook_path`** (default `/webhooks/sous-chef`) so you can build a full URL (e.g. ngrok) + path for `webhook_url` in `POST /api/runs`.

### Examples

```bash
curl -s http://127.0.0.1:8010/health
curl -s http://127.0.0.1:8010/api/config
```

With credentials set:

```bash
curl -s "http://127.0.0.1:8010/api/recipes"
curl -s "http://127.0.0.1:8010/api/recipes/schema?recipe_name=full_text_download"
```

Start a run (illustrative parameters—adjust to your Kitchen schema):

```bash
curl -s -X POST http://127.0.0.1:8010/api/runs \
  -H 'Content-Type: application/json' \
  -d '{
    "recipe_name": "full_text_download",
    "recipe_parameters": {
      "query": "...",
      "collection_ids": [38376341],
      "start_date": "2025-01-01",
      "end_date": "2025-01-31",
      "webhook_url": "https://your-service.example/webhooks/sous-chef",
      "webhook_secret": "optional"
    }
  }'
```

Build a maps-style `query` in Python using `health_state_query_for_state_name("Lagos")` and `HEALTH_STATE_COLLECTION_ID` from `app/maps_queries`, then start the **`tagged_filtered_summaries`** flow:

```bash
curl -s -X POST http://127.0.0.1:8010/api/runs \
  -H 'Content-Type: application/json' \
  -d '{
    "recipe_name": "tagged_filtered_summaries",
    "recipe_parameters": {
      "query": "<output of health_state_query_for_state_name>",
      "collection_ids": [38376341],
      "start_date": "2025-01-01",
      "end_date": "2025-01-31"
    }
  }'
```

### Design notes

- **Settings** are cached (`get_settings()`); tests that change env should call `get_settings.cache_clear()`.
- **Queue** (`run_queue`): one asyncio worker; in-memory jobs are guarded by a lock because sync handlers read status while the worker updates state.
- **Kitchen errors** → HTTP **502** with truncated detail; missing Kitchen credentials → **503** via `KitchenSettings`.

## Layout

| Path | Role |
|------|------|
| `app/main.py` | FastAPI routes → `kitchen_service` |
| `app/kitchen_service.py` | `SousChefKitchenAPIClient` wrappers |
| `app/run_queue.py` | Serial asyncio queue → `start_recipe` (demo) |
| `app/config.py` | `KITCHEN_*` settings |
| `app/schemas.py` | Request bodies |
| `app/maps_queries.py` | MediaCloud query helpers + `app/data/data_nigeria_lga.json` |
| `app/templates.py` | Parameter string interpolation helpers |

## Tests

```bash
pytest tests/
```

## Enqueue a maps experiment (queued worker)

Prerequisites: **`KITCHEN_*`** env vars set, server running (`uvicorn app.main:app --reload --port 8010`), and this package installed in your shell (`pip install -e .` from `minimal-sous-chef-reference` so `import app...` works).

The snippet builds a real **`tagged_filtered_summaries`** body using **`health_state_query_for_state_name`** (Nigeria state from `data_nigeria_lga.json`), **`POST`s** it to **`/api/queue/runs`**, prints the response, and polls **`/api/queue/jobs/{id}`** until the job finishes or fails.

```bash
export BASE_URL="${BASE_URL:-http://127.0.0.1:8010}"
export STATE_NAME="${STATE_NAME:-Lagos}"

BODY="$(python3 <<'PY'
import json
import os
from app.maps_queries import (
    HEALTH_STATE_COLLECTION_ID,
    TAGGED_FILTERED_SUMMARIES_RECIPE,
    health_state_query_for_state_name,
)

state = os.environ.get("STATE_NAME", "Lagos")
q = health_state_query_for_state_name(state)
if not q:
    raise SystemExit(f"Unknown state (not in data_nigeria_lga.json): {state!r}")
body = {
    "recipe_name": TAGGED_FILTERED_SUMMARIES_RECIPE,
    "recipe_parameters": {
        "query": q,
        "collection_ids": [HEALTH_STATE_COLLECTION_ID],
        "start_date": "2025-01-01",
        "end_date": "2025-01-31",
    },
}
print(json.dumps(body))
PY
)"

echo "POST $BASE_URL/api/queue/runs"
RESP="$(curl -sS -X POST "$BASE_URL/api/queue/runs" \
  -H 'Content-Type: application/json' \
  -d "$BODY")"
echo "$RESP"

JOB_ID="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["id"])' "$RESP")"
echo "Polling job $JOB_ID …"

while true; do
  STATUS_JSON="$(curl -sS "$BASE_URL/api/queue/jobs/$JOB_ID")"
  STATUS="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["status"])' "$STATUS_JSON")"
  echo "$STATUS_JSON"
  if [[ "$STATUS" == "completed" || "$STATUS" == "failed" ]]; then
    break
  fi
  sleep 1
done
```

Override **`BASE_URL`** or **`STATE_NAME`** when invoking: `STATE_NAME=Kano bash -c '…'` (export the vars before the heredoc block if you paste the whole script into a file).

For an immediate Kitchen submission without the queue, send the same JSON to **`POST /api/runs`** instead of **`/api/queue/runs`**.
