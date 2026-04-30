from __future__ import annotations

from collections import Counter
from typing import Any


def do_something_with_data(
    recipe_name: str,
    rendered_parameters: dict[str, str],
    input_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Toy processing step: aggregate counts by `state` / `state_code` if present,
    count rows, echo part of the resolved query if present.
    """
    by_state: Counter[str] = Counter()
    for row in input_records:
        state = None
        for key in ("state_code", "state", "region"):
            v = row.get(key)
            if v not in (None, ""):
                state = str(v)
                break
        by_state[state or "unknown"] += 1

    query_preview = rendered_parameters.get("query", "")[:200]

    return {
        "recipe_name": recipe_name,
        "row_count": len(input_records),
        "counts_by_state": dict(sorted(by_state.items())),
        "query_preview": query_preview,
        "hypothesis_template_applied": rendered_parameters.get("hypothesis_template", ""),
    }
