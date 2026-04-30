from __future__ import annotations

from typing import Any

from .maps_experiment_queries import build_location_clause


def render_parameter_templates(
    templates: dict[str, str],
    context: dict[str, Any],
) -> dict[str, str]:
    """
    Interpolate templates using Python str.format.

    - Use {key} for top-level context keys.
    - For nested values, pass dotted paths in context is not supported by format;
      instead flatten common cases: pass precomputed keys in context, or use
      replace_placeholder for legacy LOCATION_PLACEHOLDER style.

    Raises KeyError if a placeholder is missing from context.
    """
    out: dict[str, str] = {}
    for name, template in templates.items():
        out[name] = template.format(**_flatten_context_for_format(context))
    return out


def _flatten_context_for_format(context: dict[str, Any]) -> dict[str, Any]:
    """Allow format() to use dotted keys as literal key names is awkward; use flat keys."""
    flat: dict[str, Any] = dict(context)
    for k, v in context.items():
        if isinstance(v, dict):
            for inner_k, inner_v in v.items():
                flat[f"{k}_{inner_k}"] = inner_v
    return flat


def replace_named_placeholder(template: str, placeholder_name: str, value: str) -> str:
    """Replace e.g. LOCATION_PLACEHOLDER when not using str.format naming."""
    return template.replace(placeholder_name, value)


def render_maps_style_query(
    query_template: str,
    *,
    location_expression: str,
) -> str:
    """
    Mirrors the maps example: template contains LOCATION_PLACEHOLDER, filled with a
    pre-built MediaCloud-style location clause.
    """
    return replace_named_placeholder(query_template, "LOCATION_PLACEHOLDER", location_expression)
