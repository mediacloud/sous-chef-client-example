from __future__ import annotations

from app.maps_queries import (
    HEALTH_STATE_COLLECTION_ID,
    HEALTH_STATE_QUERY_TEMPLATE,
    TAGGED_FILTERED_SUMMARIES_RECIPE,
    health_state_query_for_state_name,
)
from app.templates import build_location_clause, render_maps_style_query


def test_location_and_query_template() -> None:
    loc = build_location_clause("Lagos", ["Ikeja"])
    q = render_maps_style_query("(LOCATION_PLACEHOLDER) AND x", location_expression=loc)
    assert "Lagos" in q
    assert "LOCATION_PLACEHOLDER" not in q


def test_maps_health_query_strings() -> None:
    assert "LOCATION_PLACEHOLDER" in HEALTH_STATE_QUERY_TEMPLATE
    assert "health health health" in HEALTH_STATE_QUERY_TEMPLATE
    assert HEALTH_STATE_COLLECTION_ID == 38376341
    full = health_state_query_for_state_name("Lagos")
    assert full is not None
    assert "health health health" in full
    assert "Lagos" in full
    assert "LOCATION_PLACEHOLDER" not in full


def test_tagged_filtered_summaries_is_registered_kitchen_recipe_name() -> None:
    """Kitchen / Sous-Chef register this flow as ``tagged_filtered_summaries`` (not ``..._summary``)."""
    assert TAGGED_FILTERED_SUMMARIES_RECIPE == "tagged_filtered_summaries"


def test_example_post_body_for_tagged_filtered_summaries() -> None:
    """
    Illustrative ``POST /api/runs`` JSON: maps helpers feed ``recipe_parameters.query``
    for the aboutness + summaries pipeline.
    """
    query = health_state_query_for_state_name("Lagos")
    assert query is not None
    body = {
        "recipe_name": TAGGED_FILTERED_SUMMARIES_RECIPE,
        "recipe_parameters": {
            "query": query,
            "collection_ids": [HEALTH_STATE_COLLECTION_ID],
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
        },
    }
    assert body["recipe_name"] == "tagged_filtered_summaries"
    assert "health health health" in body["recipe_parameters"]["query"]
