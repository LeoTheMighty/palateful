"""riip-3 — fraction of extracted ingredients whose `unit` is canonical.

The canonical set is the same one enumerated in extractor prompts
(`utils.services.recipe_extractors.unit_prompt.CANONICAL_UNIT_TOKENS`).

A "non-canonical" extraction is one where the LLM emitted a token outside
the enum (e.g. "tablespoon" instead of "tbsp", or a typo). `null`/empty
units are *excluded from the denominator* — they're legitimate (count
items, qualitative amounts) and shouldn't drag the compliance number
down.

Usage:
    >>> compute_unit_enum_compliance({"recipes": [...]})
    {"compliance": 0.97, "total_units": 142, "compliant": 138,
     "non_compliant_breakdown": {"tablespoon": 3, "teaspoon": 1}}
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from utils.services.recipe_extractors.unit_prompt import CANONICAL_UNIT_TOKENS

_CANONICAL_SET = frozenset(t.lower() for t in CANONICAL_UNIT_TOKENS)


def _iter_recipes(payload: Any):
    """Yield recipe dicts from either a `{"recipes": [...]}` or bare-recipe shape."""
    if isinstance(payload, dict):
        if isinstance(payload.get("recipes"), list):
            yield from (r for r in payload["recipes"] if isinstance(r, dict))
        else:
            yield payload
    elif isinstance(payload, list):
        yield from (r for r in payload if isinstance(r, dict))


def compute_unit_enum_compliance(payload: Any) -> dict[str, Any]:
    """Return compliance stats for the extracted ingredients in `payload`."""
    total = 0
    compliant = 0
    non_compliant: Counter[str] = Counter()

    for recipe in _iter_recipes(payload):
        for ing in recipe.get("ingredients") or []:
            if not isinstance(ing, dict):
                continue
            unit = ing.get("unit")
            if unit is None:
                continue
            if isinstance(unit, str) and not unit.strip():
                continue
            total += 1
            normalized = unit.strip().lower() if isinstance(unit, str) else None
            if normalized in _CANONICAL_SET:
                compliant += 1
            else:
                non_compliant[unit] += 1

    compliance = (compliant / total) if total else 1.0
    return {
        "compliance": compliance,
        "total_units": total,
        "compliant": compliant,
        "non_compliant_breakdown": dict(non_compliant),
    }
