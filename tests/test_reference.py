from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.maps_experiment_queries import (
    HEALTH_STATE_COLLECTION_ID,
    HEALTH_STATE_QUERY_TEMPLATE,
    health_state_query_for_state_name,
)
from app.templates import build_location_clause, render_maps_style_query


def test_location_and_query_template() -> None:
    loc = build_location_clause("Lagos", ["Ikeja"])
    q = render_maps_style_query("(LOCATION_PLACEHOLDER) AND x", location_expression=loc)
    assert "Lagos" in q
    assert "LOCATION_PLACEHOLDER" not in q


def test_maps_health_query_matches_results_shell() -> None:
    assert "LOCATION_PLACEHOLDER" in HEALTH_STATE_QUERY_TEMPLATE
    assert "health health health" in HEALTH_STATE_QUERY_TEMPLATE
    assert HEALTH_STATE_COLLECTION_ID == 38376341
    full = health_state_query_for_state_name("Lagos")
    assert full is not None
    assert "health health health" in full
    assert "Lagos" in full
    assert "LOCATION_PLACEHOLDER" not in full


def test_job_completes_with_webhook_attempt() -> None:
    with TestClient(app) as client:
        r = client.post(
            "/jobs",
            json={
                "recipe_name": "unit",
                "parameter_templates": {"query": "(LOCATION_PLACEHOLDER)"},
                "template_context": {"location_expression": '("Z")'},
                "input_records": [{"state_code": "Z"}],
                "webhook_url": "http://127.0.0.1:9/unreachable",
            },
        )
        assert r.status_code == 200
        jid = r.json()["id"]

        final = None
        for _ in range(200):
            g = client.get(f"/jobs/{jid}")
            assert g.status_code == 200
            final = g.json()
            if final["status"] == "completed" and final["webhook_delivered"] is not None:
                break
            time.sleep(0.01)
        else:
            pytest.fail(f"timeout last={final}")

        assert final["rendered_parameters"]["query"] == '(("Z"))'
        assert final["webhook_delivered"] is False
        assert final["webhook_error"]
