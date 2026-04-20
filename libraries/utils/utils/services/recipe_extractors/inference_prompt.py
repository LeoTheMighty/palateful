"""Field-level inference prompt rule, gated by EXTRACTOR_INFER_MISSING_FIELDS.

efi-1 — when the flag is on (default), LLM-based extractors (ai, vision,
text) get a prompt block telling the model to best-guess a fixed
allow-list of recipe-level fields when the source doesn't state them,
and to self-report every inferred field in a top-level
``inferred_fields`` array. When the flag is off, the block is empty and
downstream guardrails / penalty / persist layers treat every recipe as
non-inferred (``inferred_fields = []``).

Read at extractor-call time, not at process startup, so a flag flip via
ECS task-def takes effect on the very next extraction.

The 9-field allow-list is the single source of truth — guardrails, the
submit-correction endpoint, and the Flutter contract test all import
``INFERABLE_FIELDS`` from here.
"""

from __future__ import annotations

import os

INFERABLE_FIELDS: tuple[str, ...] = (
    "prep_time_minutes",
    "cook_time_minutes",
    "total_time_minutes",
    "servings",
    "description",
    "cuisine",
    "category",
    "primary_vibe",
    "secondary_vibe",
)

_INFERENCE_RULE = (
    "- Field-level inference for recipe-root metadata ONLY:\n"
    "  You MAY best-guess a plausible value for the following fields "
    "when the source does not explicitly state them, provided the guess "
    "is grounded in visible recipe content (ingredient complexity, step "
    "count, implied pan / serving size, cuisine cues, etc.): "
    "prep_time_minutes, cook_time_minutes, total_time_minutes, "
    "servings, description, cuisine, category, primary_vibe, "
    "secondary_vibe.\n"
    "  NEVER infer name, ingredients, steps, source_url, author, image_url, "
    "or keywords — their absence stays absence.\n"
    "  For every field you infer, add its schema name to a top-level "
    '"inferred_fields" array on the recipe object.\n'
    '  ALWAYS emit "inferred_fields" as an array, even when empty (use '
    "[], never null).\n"
    "  Example: a cookbook page showing a 9x13 brownie recipe with "
    '"Bake at 350°F for 25-30 minutes" but no printed servings or prep '
    'time → emit cook_time_minutes: 27 (midpoint), servings: 16 '
    "(9x13 pan implies ~16 squares), prep_time_minutes: 15 (ingredient "
    'complexity), inferred_fields: ["cook_time_minutes", "servings", '
    '"prep_time_minutes"].'
)


def infer_missing_fields() -> bool:
    """Read the feature flag at call time. Default-on."""
    raw = os.environ.get("EXTRACTOR_INFER_MISSING_FIELDS", "true")
    return raw.strip().lower() not in ("false", "0", "no", "off")


def inference_rule() -> str:
    """Return the prompt fragment instructing best-guess inference.

    Empty string when the flag is OFF — callers splice the result in as
    ``{inference_rule()}`` and expect no content when disabled.
    """
    if infer_missing_fields():
        return _INFERENCE_RULE
    return ""
