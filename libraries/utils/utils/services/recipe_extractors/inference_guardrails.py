"""Server-authoritative clamp + truncate + validate for inferred fields.

efi-1 — when the LLM emits a top-level ``inferred_fields`` array listing
the recipe-root fields it best-guessed, we run each inferred value
through the rules below before persisting. The extractor prompt tells
the model to produce plausible values, but prompts are advisory, not
guarantees — a stray 9999-minute cook time or a 1200-char description
must be squeezed into shape server-side so the UI stays honest.

Rules (per field):

- prep_time_minutes: int, clamped to [1, 240]
- cook_time_minutes: int, clamped to [1, 720]
- total_time_minutes: int, clamped to [1, 960]
- servings: int, clamped to [1, 24]
- description: str, truncated to 240 chars at the nearest word boundary
- cuisine: str, truncated to 40 chars
- category: str, truncated to 40 chars
- primary_vibe, secondary_vibe: ``validate_vibe()`` — invalid → drop to
  ``None`` AND remove from ``inferred_fields``

Every clamp / truncate / drop writes one audit row via
``log_inferred_field_clamp``. Design principle 8 from the epic says the
feedback log IS the killer feature — we want comprehensive signal even
when the dashboard that reads it doesn't exist yet.

This module is called by ``extract_recipe_task`` after the extractor
returns but before the confidence score resolves (so the penalty sees
the post-guardrail ``inferred_fields`` count, not the pre-guardrail one
— vibes that drop should also stop being penalized).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from utils.logging.inference_logging import log_inferred_field_clamp
from utils.services.recipe_extractors.inference_prompt import INFERABLE_FIELDS

if TYPE_CHECKING:
    from utils.services.recipe_extractors.base import ExtractedRecipe

# Per-field numeric clamp ranges (inclusive).
_NUMERIC_RANGES: dict[str, tuple[int, int]] = {
    "prep_time_minutes": (1, 240),
    "cook_time_minutes": (1, 720),
    "total_time_minutes": (1, 960),
    "servings": (1, 24),
}

# Per-field string truncation caps.
_STRING_CAPS: dict[str, int] = {
    "description": 240,
    "cuisine": 40,
    "category": 40,
}

_VIBE_FIELDS: frozenset[str] = frozenset({"primary_vibe", "secondary_vibe"})


def _truncate_at_word_boundary(value: str, cap: int) -> str:
    """Truncate ``value`` to at most ``cap`` chars, preferring a word boundary.

    If the cap lands mid-word, back up to the nearest space. If the
    word-boundary cut would leave an implausibly short result (less
    than 80% of the cap), fall back to a hard truncate at ``cap`` — we'd
    rather ship a mid-word cut than a 3-word stub when the LLM emitted
    a description with very long words.
    """
    if len(value) <= cap:
        return value
    window = value[:cap]
    last_space = window.rfind(" ")
    min_floor = int(cap * 0.8)
    if last_space >= min_floor:
        return window[:last_space].rstrip()
    return window


def _clamp_numeric(
    raw: Any, lo: int, hi: int
) -> tuple[int | None, bool]:
    """Coerce ``raw`` to int, clamp to [lo, hi].

    Returns ``(clamped_value, was_changed)``. If the input can't be
    coerced to a real integer (None, bool, non-numeric string, NaN),
    returns ``(None, True)`` so the caller can drop the value.
    """
    if raw is None:
        return (None, False)
    if isinstance(raw, bool):
        # bool is a subclass of int; reject it so a stray True/False
        # doesn't silently become 1 / 0.
        return (None, True)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return (None, True)

    if value < lo:
        return (lo, True)
    if value > hi:
        return (hi, True)
    return (value, False)


def apply_guardrails(
    recipe: ExtractedRecipe,
    import_item_id: str | None,
) -> ExtractedRecipe:
    """Mutate ``recipe`` in place, enforcing per-field clamp / truncate / drop rules.

    Iterates the ``inferred_fields`` list in place and, per field, reads
    the corresponding attribute off ``recipe``, reshapes it according to
    the rules above, and writes the reshaped value back. Vibes that
    fail validation are removed from ``inferred_fields`` entirely (the
    attribute is also set to ``None``). Every reshape writes one audit
    row via ``log_inferred_field_clamp``.

    Returns the same recipe object for ergonomic chaining.

    ``import_item_id`` may be ``None`` for pre-persistence contexts
    (unit tests, dry-run eval) — the audit row's ``import_item_id``
    column stays null in that case.
    """
    inferred = list(getattr(recipe, "inferred_fields", []) or [])
    if not inferred:
        return recipe

    # Preserve insertion order while removing vibes that fail validation.
    kept: list[str] = []
    for field in inferred:
        if field not in INFERABLE_FIELDS:
            # Defense in depth — extractor parsing already filters, but
            # guard here too so a manually-constructed recipe can't sneak
            # a bogus field past us.
            continue

        if field in _NUMERIC_RANGES:
            raw = getattr(recipe, field, None)
            lo, hi = _NUMERIC_RANGES[field]
            clamped, changed = _clamp_numeric(raw, lo, hi)
            if changed:
                # bool falls through `_clamp_numeric` as a type violation,
                # not an out-of-range issue — surface that distinction in
                # the audit row so the correction-log dashboard can tell
                # the two apart.
                reason = (
                    "invalid_type" if isinstance(raw, bool) else "out_of_range"
                )
                log_inferred_field_clamp(
                    import_item_id=import_item_id,
                    field=field,
                    raw=raw,
                    clamped_or_dropped=clamped,
                    reason=reason,
                )
                setattr(recipe, field, clamped)
            # Numeric fields always stay in `inferred_fields`. A coerce
            # failure (`clamped is None`) leaves the attribute None but
            # keeps the provenance signal — the model still *claimed* to
            # have inferred this field.
            kept.append(field)
            continue

        if field in _STRING_CAPS:
            raw = getattr(recipe, field, None)
            cap = _STRING_CAPS[field]
            if raw is None:
                kept.append(field)
                continue
            raw_str = raw if isinstance(raw, str) else str(raw)
            if len(raw_str) > cap:
                truncated = (
                    _truncate_at_word_boundary(raw_str, cap)
                    if field == "description"
                    else raw_str[:cap]
                )
                log_inferred_field_clamp(
                    import_item_id=import_item_id,
                    field=field,
                    raw=raw_str,
                    clamped_or_dropped=truncated,
                    reason="too_long",
                )
                setattr(recipe, field, truncated)
            kept.append(field)
            continue

        if field in _VIBE_FIELDS:
            # Local import — `validate_vibe` lives in base.py next to
            # ExtractedRecipe, and base.py is imported by this module's
            # TYPE_CHECKING guard.
            from utils.services.recipe_extractors.base import validate_vibe

            raw = getattr(recipe, field, None)
            validated = validate_vibe(raw) if raw is not None else None
            if raw is not None and validated is None:
                log_inferred_field_clamp(
                    import_item_id=import_item_id,
                    field=field,
                    raw=raw,
                    clamped_or_dropped=None,
                    reason="invalid_vibe",
                )
                setattr(recipe, field, None)
                # Vibes that drop are REMOVED from inferred_fields — the
                # field is no longer inferred, it's simply absent.
                continue
            kept.append(field)
            continue

    recipe.inferred_fields = kept  # type: ignore[attr-defined]
    return recipe
