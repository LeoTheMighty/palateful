"""Heuristic fallback for ``confidence_score``.

irrd-3 — when the LLM declined to self-assess (`confidence_score = null`)
or emitted a malformed value (non-numeric, out of [0, 1]), we synthesize
a score from structural signals on the extracted recipe. When the flag
``EXTRACTOR_EMIT_CONFIDENCE`` is off, this path is always taken.

The calibration weights below are starter values. The epic requires a
pre-merge gate that verifies MAE ≤ 0.3 vs ground-truth F1 across the
fixture suite; when/if that gate fires (deferred under irrd-3a), weights
get tuned and land in the same commit.
"""

from __future__ import annotations

from typing import Any

# Weights sum to 1.0. Keep them aligned with
# `services/eval/src/metrics/confidence_calibration.py` when the gate lands.
_W_INGREDIENTS = 0.4
_W_TITLE = 0.3
_W_STEPS = 0.3


def _extract_ingredient_signal(recipe: Any) -> float:
    """Fraction of ingredients that have a numeric quantity.

    Used as a proxy for extraction fidelity at the extract stage (the
    post-match `matched_ingredient_id` signal is not yet available when
    the heuristic fires). Empty ingredient lists score 0.
    """
    ingredients = _get(recipe, "ingredients") or []
    if not ingredients:
        return 0.0

    with_quantity = 0
    for ing in ingredients:
        qty = _get(ing, "quantity")
        # `bool` is a subclass of `int` in Python, so guard explicitly —
        # a stray `true`/`false` from the LLM must not count as a real
        # quantity.
        if isinstance(qty, int | float) and not isinstance(qty, bool):
            with_quantity += 1
    return min(with_quantity / max(len(ingredients), 1), 1.0)


def _extract_title_signal(recipe: Any) -> float:
    """1.0 when there is a non-empty, non-'Untitled' title; else 0.0."""
    title = _get(recipe, "name")
    if not isinstance(title, str):
        return 0.0
    cleaned = title.strip()
    if not cleaned or cleaned.lower() == "untitled recipe":
        return 0.0
    return 1.0


def _extract_step_signal(recipe: Any) -> float:
    """min(step_count / 3, 1.0) — 3+ steps is saturated."""
    steps = _get(recipe, "steps")
    if isinstance(steps, list) and steps:
        return min(len(steps) / 3.0, 1.0)

    # Fallback: count lines in the legacy `instructions` string.
    instructions = _get(recipe, "instructions")
    if isinstance(instructions, str) and instructions.strip():
        lines = [ln for ln in instructions.splitlines() if ln.strip()]
        return min(max(len(lines), 1) / 3.0, 1.0)

    return 0.0


def compute_heuristic_confidence(recipe: Any) -> float:
    """Compute the fallback confidence score for one recipe.

    Accepts either an ``ExtractedRecipe`` dataclass or a plain dict
    (``parsed_recipe`` JSON) so callers can run the heuristic before OR
    after serialization. Clamped to [0.0, 1.0].
    """
    ing_signal = _extract_ingredient_signal(recipe)
    title_signal = _extract_title_signal(recipe)
    step_signal = _extract_step_signal(recipe)

    score = (
        _W_INGREDIENTS * ing_signal
        + _W_TITLE * title_signal
        + _W_STEPS * step_signal
    )
    # Clamp. The weights-sum constraint keeps this in [0, 1] already,
    # but clamp defensively against future weight edits.
    return max(0.0, min(1.0, score))


def normalize_model_confidence(value: Any) -> float | None:
    """Coerce a raw model-emitted value to a valid float in [0, 1] or None.

    Accepts:
      - `None` -> None (caller triggers heuristic)
      - bool -> None (bool is numeric in Python but not a valid score)
      - int/float in [0, 1] -> float
      - numeric string in [0, 1] -> float
      - anything else (out-of-range, non-numeric, NaN) -> None
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        try:
            f = float(value)
        except (TypeError, ValueError):
            return None
        if f != f:  # NaN
            return None
        if 0.0 <= f <= 1.0:
            return f
        return None
    if isinstance(value, str):
        try:
            f = float(value.strip())
        except (TypeError, ValueError):
            return None
        if 0.0 <= f <= 1.0:
            return f
        return None
    return None


def _get(obj: Any, name: str) -> Any:
    """Attribute-or-dict accessor."""
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def resolve_confidence(
    raw_data: dict | None,
    recipe: Any,
) -> tuple[float, str]:
    """Decide the final ``(confidence_score, confidence_source)`` pair.

    ``raw_data`` is the unparsed recipe object the LLM emitted (or any
    dict carrying ``confidence_score`` / ``confidence_source`` keys).
    ``recipe`` is the parsed ``ExtractedRecipe`` (or equivalent) used to
    compute the heuristic fallback when the model declined or returned
    garbage.

    Decision tree:
      1. Flag off (model was never asked) -> always heuristic.
      2. Model emitted a valid float in [0, 1] -> use it, source="model".
      3. Otherwise (null / malformed / flag on but nothing emitted) ->
         heuristic.

    Returns a fully-resolved tuple — never None — so callers can set
    both fields on the persisted ``parsed_recipe`` unconditionally.
    """
    from utils.services.recipe_extractors.confidence_prompt import emit_confidence

    if emit_confidence() and isinstance(raw_data, dict):
        model_score = normalize_model_confidence(raw_data.get("confidence_score"))
        if model_score is not None:
            return (model_score, "model")

    return (compute_heuristic_confidence(recipe), "heuristic")
