"""Canonical-unit prompt rule, gated by the EXTRACTOR_EMIT_CANONICAL_UNITS flag.

riip-3 — when the flag is on (default), all three extractors enumerate the
canonical token list verbatim in the prompt's "unit:" rule, so the LLM
stops emitting full words ("tablespoon" → "tbsp"). When the flag is off,
extractors fall back to the prior freeform instruction so we can flip
back via ECS task def without a redeploy if the prompt change regresses.

Read at extractor-call time, not at process startup, so a flag flip
applies to the very next request.
"""

from __future__ import annotations

import os

# Kept in sync with `libraries/utils/utils/services/units/normalize.py`'s
# canonical set and the `units` table seed in
# `services/migrator/migrations/versions/20260418040000_create_unit_aliases.py`.
CANONICAL_UNIT_TOKENS: tuple[str, ...] = (
    "tsp",
    "tbsp",
    "cup",
    "fl oz",
    "ml",
    "l",
    "g",
    "kg",
    "oz",
    "lb",
    "each",
    "pinch",
    "dash",
    "clove",
    "slice",
    "mg",
    "gallon",
    "quart",
    "pint",
)


_CANONICAL_RULE = (
    '- "unit": use EXACTLY one of these tokens — '
    + ", ".join(f"`{t}`" for t in CANONICAL_UNIT_TOKENS)
    + ". Do not write out full words. Do not add trailing punctuation. "
    'Use null for count items ("3 large eggs" -> unit: null) or when there is '
    "no unit. Never include the number or the ingredient name here."
)


def emit_canonical_units() -> bool:
    """Read the feature flag at call time. Default-on."""
    raw = os.environ.get("EXTRACTOR_EMIT_CANONICAL_UNITS", "true")
    return raw.strip().lower() not in ("false", "0", "no", "off")


def unit_rule(*, freeform_fallback: str) -> str:
    """Return the prompt's `- "unit": ...` line.

    `freeform_fallback` is the legacy instruction that was hand-tuned per
    extractor. We keep using it when the flag is OFF so the rollback path
    is the previous behavior verbatim.
    """
    if emit_canonical_units():
        return _CANONICAL_RULE
    return freeform_fallback
