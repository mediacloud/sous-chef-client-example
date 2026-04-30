"""
MediaCloud query helpers for Nigeria state/LGA–scoped “health” style maps runs.

Provides the shared ``query`` template, a default story collection id, and geography
from ``app/data/data_nigeria_lga.json`` to fill ``LOCATION_PLACEHOLDER``.

**Kitchen recipe names** (registered flows in Sous-Chef / Kitchen) — use as
``recipe_name`` in ``POST /api/runs``:

- ``FULL_TEXT_DOWNLOAD_RECIPE`` — download stories matching the query.
- ``TAGGED_FILTERED_SUMMARIES_RECIPE`` — aboutness + zero-shot tags + summaries (the usual “maps” pipeline).

Use the resulting strings in ``recipe_parameters`` together with dates, ``webhook_url``,
``b2_object_prefix``, etc.; this module only builds ``query`` + documents collection id.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

# Registered Kitchen flow names (see ``sous_chef.flows`` — names must match Kitchen).
FULL_TEXT_DOWNLOAD_RECIPE = "full_text_download"
TAGGED_FILTERED_SUMMARIES_RECIPE = "tagged_filtered_summaries"

# Default MediaCloud collection for the health-maps style queries (Nigeria National collection).
HEALTH_STATE_COLLECTION_ID = 38376341

# Location clause replaces LOCATION_PLACEHOLDER (see ``build_state_location_placeholder``).
HEALTH_STATE_QUERY_TEMPLATE = '(LOCATION_PLACEHOLDER) AND "health health health"~1000'


@dataclass
class GeographyTarget:
    state_name: str
    lga_names: List[str]


def _data_dir() -> Path:
    return Path(__file__).resolve().parent / "data"


def load_state_geographies() -> List[GeographyTarget]:
    """Load Nigerian state → LGA mapping from ``app/data/data_nigeria_lga.json``."""
    mapping_path = _data_dir() / "data_nigeria_lga.json"
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    targets: List[GeographyTarget] = []
    for state_name, lgas in mapping.items():
        if not isinstance(lgas, list):
            continue
        targets.append(GeographyTarget(state_name=state_name, lga_names=[str(lga) for lga in lgas]))
    return targets


def geography_for_state_name(state_name: str) -> GeographyTarget | None:
    """Return the geography row for a state, or None if unknown."""
    norm = state_name.strip()
    for g in load_state_geographies():
        if g.state_name.strip().lower() == norm.lower():
            return g
    return None


def build_state_location_placeholder(target: GeographyTarget) -> str:
    """
    Build the LOCATION_PLACEHOLDER expression: ``(STATE) AND (LGA1 OR LGA2 OR ...)``.
    """
    state_term = f'"{target.state_name}"'
    lga_terms = [f'"{lga}"' for lga in target.lga_names]
    if not lga_terms:
        return state_term
    lga_clause = " OR ".join(lga_terms)
    return f"({state_term}) AND ({lga_clause})"


def build_location_clause(state_name: str, lga_names: list[str]) -> str:
    """Convenience: location expression from plain strings (re-exported via ``templates``)."""
    return build_state_location_placeholder(GeographyTarget(state_name=state_name, lga_names=list(lga_names)))


def health_state_query_for_target(target: GeographyTarget) -> str:
    """Full MediaCloud ``query`` string for one state + LGAs."""
    location_expr = build_state_location_placeholder(target)
    return HEALTH_STATE_QUERY_TEMPLATE.replace("LOCATION_PLACEHOLDER", location_expr)


def health_state_query_for_state_name(state_name: str) -> str | None:
    """Build the full query for a state present in ``data_nigeria_lga.json``."""
    target = geography_for_state_name(state_name)
    if target is None:
        return None
    return health_state_query_for_target(target)
