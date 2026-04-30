"""
Thin wrapper around ``SousChefKitchenAPIClient``.

Every HTTP route in this app should go through these helpers so the reference stays
centered on ``sous-chef-kitchen-client``.
"""

from __future__ import annotations

from typing import Any

from sous_chef_kitchen_client import SousChefKitchenAPIClient

from .config import Settings


def build_client(settings: Settings) -> SousChefKitchenAPIClient:
    return SousChefKitchenAPIClient(
        auth_email=settings.kitchen_auth_email or None,
        auth_key=settings.kitchen_auth_key or None,
        base_url=settings.kitchen_base_url,
    )


def list_recipes(settings: Settings) -> dict[str, Any]:
    return build_client(settings).recipe_list()


def recipe_schema(settings: Settings, recipe_name: str) -> dict[str, Any]:
    return build_client(settings).recipe_schema(recipe_name)


def start_recipe(
    settings: Settings,
    recipe_name: str,
    recipe_parameters: dict[str, Any],
) -> dict[str, Any]:
    return build_client(settings).start_recipe(recipe_name, recipe_parameters)


def fetch_run(settings: Settings, run_id: str) -> dict[str, Any]:
    return build_client(settings).fetch_run_by_id(run_id)


def fetch_run_artifacts(settings: Settings, run_id: str) -> dict[str, Any]:
    return build_client(settings).fetch_run_artifacts(run_id)


def validate_auth(settings: Settings):
    return build_client(settings).validate_auth()
