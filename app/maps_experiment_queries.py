"""
Maps experiment MediaCloud query helpers.

Copied from ``sous-chef-results-shell/backend/app/maps_config.py`` (constants +
location placeholder logic). Used by both ``full_text_download`` and
``tagged_filtered_summaries`` maps pipelines for the same base ``query`` string.

See also: ``app/data/data_nigeria_lga.json`` (state → LGA names), mirrored from the results shell.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

# --- Experiment identifiers (Results Shell ``maps_config.EXPERIMENTS``) ---

HEALTH_STATE_EXPERIMENT_ID = "state_health_health_health_two"
ABOUTNESS_ZEROSHOT_STATE_EXPERIMENT_ID = "state_health_aboutness_zeroshot_v1"

# Older Kitchen registrations used this recipe name; current flow uses ``tagged_filtered_summaries``.
LEGACY_TAGGED_FILTERED_SUMMARIES_RECIPE = "aboutness_filtered_summaries"

MAPS_FULL_TEXT_RECIPE_NAME = "full_text_download"
MAPS_TAGGED_FILTERED_SUMMARIES_RECIPE_NAME = "tagged_filtered_summaries"

# --- Query template & collection (health maps experiments) ---

# Location clause replaces LOCATION_PLACEHOLDER (see ``build_state_location_placeholder``).
HEALTH_STATE_QUERY_TEMPLATE = '(LOCATION_PLACEHOLDER) AND "health health health"~1000'

HEALTH_STATE_COLLECTION_ID = 38376341


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
    Build the LOCATION_PLACEHOLDER expression for state-level experiments.

    Mirrors geotagging intent: ``(STATE) AND (LGA1 OR LGA2 OR ...)``.
    """
    state_term = f'"{target.state_name}"'
    lga_terms = [f'"{lga}"' for lga in target.lga_names]
    if not lga_terms:
        return state_term
    lga_clause = " OR ".join(lga_terms)
    return f"({state_term}) AND ({lga_clause})"


def build_location_clause(state_name: str, lga_names: list[str]) -> str:
    """Convenience: same placeholder string from plain strings (see ``templates.build_location_clause``)."""
    return build_state_location_placeholder(GeographyTarget(state_name=state_name, lga_names=list(lga_names)))


def health_state_query_for_target(target: GeographyTarget) -> str:
    """Full MediaCloud ``query`` string for the health maps experiments for one state."""
    location_expr = build_state_location_placeholder(target)
    return HEALTH_STATE_QUERY_TEMPLATE.replace("LOCATION_PLACEHOLDER", location_expr)


def health_state_query_for_state_name(state_name: str) -> str | None:
    """Resolve query for a known state from ``data_nigeria_lga.json``."""
    target = geography_for_state_name(state_name)
    if target is None:
        return None
    return health_state_query_for_target(target)
