# Minimal Sous-Chef reference

Small FastAPI app showing the same moving parts as `sous-chef-results-shell`, without Kitchen, SQL, maps UI, or resync logic:

1. **HTTP API** — submit a “recipe” name and parameter templates.
2. **Template interpolation** — `str.format`-style `{keys}` plus optional `LOCATION_PLACEHOLDER` replacement (maps-style).
3. **Queue** — `asyncio` queue + single background worker (conceptually like queued runs → worker promotes).
4. **Process data** — toy aggregation over optional input rows.
5. **Webhook callback** — optional HTTP POST when the job finishes.

## Run

```bash
cd minimal-sous-chef-reference
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
uvicorn app.main:app --reload --port 8010
```

## Examples

**Health check**

```bash
curl -s http://127.0.0.1:8010/health
```

**Simple `{placeholder}` templates + sample rows**

```bash
curl -s -X POST http://127.0.0.1:8010/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "recipe_name": "demo_recipe",
    "parameter_templates": {
      "topic": "climate",
      "hypothesis_template": "This text is about {label}"
    },
    "template_context": {
      "label": "health"
    },
    "input_records": [
      {"state_code": "CA", "text": "..."},
      {"state_code": "CA", "text": "..."},
      {"state_code": "NY", "text": "..."}
    ]
  }'
```

**Maps-style query** — template contains `LOCATION_PLACEHOLDER`; pass `location_expression` in context (or build it yourself). Same pattern as `HEALTH_STATE_QUERY_TEMPLATE` in `sous-chef-results-shell/backend/app/maps_config.py`.

```bash
curl -s -X POST http://127.0.0.1:8010/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "recipe_name": "full_text_download",
    "parameter_templates": {
      "query": "(LOCATION_PLACEHOLDER) AND \"health health health\"~1000",
      "start_date": "2025-01-01",
      "end_date": "2025-01-31"
    },
    "template_context": {
      "location_expression": "(\"Lagos\") AND (\"Ikeja\" OR \"Surulere\")"
    },
    "input_records": [{"state_code": "Lagos"}]
  }'
```

**Webhook callback** — set `webhook_url` to a reachable URL. For local testing, point at the included echo route:

```bash
curl -s -X POST http://127.0.0.1:8010/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "recipe_name": "with_callback",
    "parameter_templates": {"note": "{msg}"},
    "template_context": {"msg": "hello"},
    "input_records": [],
    "webhook_url": "http://127.0.0.1:8010/demo/webhook-echo",
    "webhook_secret": "optional-shared-secret"
  }'
```

Then `GET /jobs/{id}` to see `webhook_delivered` / `webhook_error`. The job’s `status` becomes `completed` only after the webhook attempt finishes, so `webhook_delivered` is always populated once you see `completed` (unlike a fire-and-forget callback that could race with polling).

## Maps experiment queries (from Results Shell)

Constants and location clauses mirror [`../sous-chef-results-shell/backend/app/maps_config.py`](../sous-chef-results-shell/backend/app/maps_config.py):

| Symbol | Meaning |
|--------|---------|
| `HEALTH_STATE_QUERY_TEMPLATE` | `'(LOCATION_PLACEHOLDER) AND "health health health"~1000'` |
| `HEALTH_STATE_COLLECTION_ID` | `38376341` |
| `HEALTH_STATE_EXPERIMENT_ID` | `"state_health_health_health_two"` |
| `ABOUTNESS_ZEROSHOT_STATE_EXPERIMENT_ID` | `"state_health_aboutness_zeroshot_v1"` |

Bundled data: `app/data/data_nigeria_lga.json` (state → LGAs). Helpers:

- `load_state_geographies()` — all states from JSON  
- `health_state_query_for_state_name("Lagos")` — full MediaCloud `query` for that state  
- `build_state_location_placeholder(GeographyTarget(...))` — `LOCATION_PLACEHOLDER` text only  

The job runner still uses generic templates in `app/templates.py`; import `app.maps_experiment_queries` when you want the real maps strings.

## Layout

| Module        | Role |
|---------------|------|
| `app/main.py` | Routes |
| `app/store.py` | In-memory job records |
| `app/queue.py` | Worker + optional webhook POST |
| `app/templates.py` | Parameter interpolation |
| `app/maps_experiment_queries.py` | Maps MediaCloud query template + Nigeria geography |
| `app/processor.py` | Toy “do something with data” |
| `app/schemas.py` | Pydantic models |

Production code would swap the in-memory store for SQL, talk to Kitchen instead of a local processor, and align webhook JSON with the real Kitchen payload shape.
