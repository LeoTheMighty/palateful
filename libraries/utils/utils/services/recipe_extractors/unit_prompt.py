"""Canonical-unit prompt rule, gated by the EXTRACTOR_EMIT_CANONICAL_UNITS
and EXTRACTOR_SOFTEN_UNIT_RULE flags.

riip-3 landed the hard-canonical rule (``_CANONICAL_RULE``): LLM MUST use
one of 19 canonical tokens. Dogfood surfaced that this was too
restrictive — "1 clove garlic" folded `clove` into the name, "2 stalks
celery" lost the unit entirely.

eri-1 adds a SOFTENED variant (``_SOFTENED_RULE``) that keeps the 19
tokens as a *preferred* hint but lets the LLM emit freeform words
(stalk, bunch, sprig, head, can, packet, stick, sheet, strip, piece,
sachet, jar, bottle, bar, drop) when the source uses them. It also
biases toward convertible units when ambiguous so later US↔metric
conversion has something to hang off.

Flag precedence, checked at call time so a task-def flip applies to the
next request without a redeploy:

1. ``EXTRACTOR_SOFTEN_UNIT_RULE`` (default on)      -> ``_SOFTENED_RULE``
2. ``EXTRACTOR_EMIT_CANONICAL_UNITS`` (default on)  -> ``_CANONICAL_RULE``
3. neither                                          -> ``freeform_fallback``
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

# Convertible units — when the source is ambiguous between one of these and
# a count unit, the softened rule biases toward the convertible one. This is
# documented in the prompt so the LLM can honor it.
_CONVERTIBLE_UNITS: tuple[str, ...] = (
    "cup", "tbsp", "tsp", "ml", "l", "g", "kg", "oz", "lb", "fl oz",
)

# Freeform words we explicitly allow in the softened rule. These match the
# 15 new rows seeded into `units` in eri-4a and the plural→singular aliases
# in eri-4b.
_FREEFORM_ALLOWED: tuple[str, ...] = (
    "stalk", "bunch", "sprig", "head", "can", "packet", "stick",
    "sheet", "strip", "piece", "sachet", "jar", "bottle", "bar", "drop",
)


_CANONICAL_RULE = (
    '- "unit": use EXACTLY one of these tokens — '
    + ", ".join(f"`{t}`" for t in CANONICAL_UNIT_TOKENS)
    + ". Do not write out full words. Do not add trailing punctuation. "
    'Use null for count items ("3 large eggs" -> unit: null) or when there is '
    "no unit. Never include the number or the ingredient name here."
)


_SOFTENED_RULE = (
    '- "unit": prefer one of these tokens where applicable — '
    + ", ".join(f"`{t}`" for t in CANONICAL_UNIT_TOKENS)
    + ". If the source uses a more accurate freeform unit word that isn't in "
    "this list (e.g., "
    + ", ".join(f"`{w}`" for w in _FREEFORM_ALLOWED)
    + "), emit that word literally in lowercase singular form. When the "
    "source is ambiguous between a convertible unit ("
    + ", ".join(f"`{u}`" for u in _CONVERTIBLE_UNITS)
    + ") and a count unit, prefer the convertible one — it lets us convert "
    'later. Use null for count items ("3 large eggs" -> unit: null) or when '
    'the item itself is uncountable ("salt to taste" -> unit: null). Never '
    "include the number or the ingredient name here."
)


def emit_canonical_units() -> bool:
    """Read the canonical-unit flag at call time. Default-on."""
    raw = os.environ.get("EXTRACTOR_EMIT_CANONICAL_UNITS", "true")
    return raw.strip().lower() not in ("false", "0", "no", "off")


def soften_unit_rule() -> bool:
    """Read the softened-rule flag at call time. Default-on."""
    raw = os.environ.get("EXTRACTOR_SOFTEN_UNIT_RULE", "true")
    return raw.strip().lower() not in ("false", "0", "no", "off")


def unit_rule(*, freeform_fallback: str) -> str:
    """Return the prompt's `- "unit": ...` line.

    Precedence (see module docstring): SOFTEN > CANONICAL > freeform.
    ``freeform_fallback`` is the per-extractor legacy instruction used
    when both flags are off so the pre-riip-3 rollback path is exact.
    """
    if soften_unit_rule():
        return _SOFTENED_RULE
    if emit_canonical_units():
        return _CANONICAL_RULE
    return freeform_fallback
