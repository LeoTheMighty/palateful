"""Scoring functions for recipe extraction evaluation.

Compares extracted recipe data against ground truth and produces
per-dimension scores plus an overall F1.
"""

from __future__ import annotations

import difflib
import re
from typing import Any

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UNIT_ALIASES: dict[str, str] = {
    "cups": "cup",
    "tablespoons": "tablespoon",
    "tbsp": "tablespoon",
    "tbsps": "tablespoon",
    "teaspoons": "teaspoon",
    "tsp": "teaspoon",
    "tsps": "teaspoon",
    "ounces": "ounce",
    "oz": "ounce",
    "pounds": "pound",
    "lbs": "pound",
    "lb": "pound",
    "grams": "gram",
    "g": "gram",
    "kilograms": "kilogram",
    "kg": "kilogram",
    "milliliters": "milliliter",
    "ml": "milliliter",
    "liters": "liter",
    "l": "liter",
    "cloves": "clove",
    "slices": "slice",
    "pieces": "piece",
    "pinches": "pinch",
    "cans": "can",
    "packages": "package",
    "pkgs": "package",
    "bunches": "bunch",
    "stalks": "stalk",
    "sprigs": "sprig",
    "dashes": "dash",
    "heads": "head",
}


def _normalize_unit(unit: str | None) -> str:
    """Normalise a unit string for comparison (lowercase, singularise)."""
    if not unit:
        return ""
    u = unit.strip().lower()
    return _UNIT_ALIASES.get(u, u)


def _fuzzy_ratio(a: str, b: str) -> float:
    """Return SequenceMatcher ratio between two strings (0-1)."""
    return difflib.SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _normalize_name(name: str | None) -> str:
    """Lowercase, strip, collapse whitespace."""
    if not name:
        return ""
    return re.sub(r"\s+", " ", name.strip().lower())


# ---------------------------------------------------------------------------
# Ingredient matching
# ---------------------------------------------------------------------------

def _match_ingredients(
    extracted: list[dict[str, Any]],
    expected: list[dict[str, Any]],
    name_threshold: float = 0.8,
) -> tuple[list[tuple[dict, dict]], list[dict], list[dict]]:
    """Match extracted ingredients to expected by fuzzy name match.

    Returns (matched_pairs, unmatched_extracted, unmatched_expected).
    """
    used_expected: set[int] = set()
    matched: list[tuple[dict, dict]] = []
    unmatched_extracted: list[dict] = []

    for ext in extracted:
        ext_name = _normalize_name(ext.get("name") or ext.get("text", ""))
        best_idx = -1
        best_ratio = 0.0

        for i, exp in enumerate(expected):
            if i in used_expected:
                continue
            exp_name = _normalize_name(exp.get("name") or exp.get("text", ""))
            ratio = _fuzzy_ratio(ext_name, exp_name)
            if ratio > best_ratio:
                best_ratio = ratio
                best_idx = i

        if best_idx >= 0 and best_ratio >= name_threshold:
            used_expected.add(best_idx)
            matched.append((ext, expected[best_idx]))
        else:
            unmatched_extracted.append(ext)

    unmatched_expected = [
        exp for i, exp in enumerate(expected) if i not in used_expected
    ]
    return matched, unmatched_extracted, unmatched_expected


# ---------------------------------------------------------------------------
# Per-dimension scoring helpers
# ---------------------------------------------------------------------------

def _score_ingredients_precision(
    extracted: list[dict[str, Any]],
    expected: list[dict[str, Any]],
) -> float:
    """Precision: fraction of extracted ingredients that match an expected one."""
    if not extracted:
        return 1.0 if not expected else 0.0
    matched, _, _ = _match_ingredients(extracted, expected)
    return len(matched) / len(extracted)


def _score_ingredients_recall(
    extracted: list[dict[str, Any]],
    expected: list[dict[str, Any]],
) -> float:
    """Recall: fraction of expected ingredients found in extracted."""
    if not expected:
        return 1.0
    matched, _, _ = _match_ingredients(extracted, expected)
    return len(matched) / len(expected)


def _score_amounts_accuracy(
    extracted: list[dict[str, Any]],
    expected: list[dict[str, Any]],
) -> float:
    """For matched ingredients, check quantity + unit agreement."""
    matched, _, _ = _match_ingredients(extracted, expected)
    if not matched:
        return 0.0

    correct = 0
    for ext, exp in matched:
        qty_ok = _quantities_match(ext.get("quantity"), exp.get("quantity"))
        unit_ok = _normalize_unit(ext.get("unit")) == _normalize_unit(exp.get("unit"))
        if qty_ok and unit_ok:
            correct += 1

    return correct / len(matched)


def _quantities_match(
    a: float | int | str | None,
    b: float | int | str | None,
    tolerance: float = 0.01,
) -> bool:
    """Compare two quantities with tolerance."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        fa, fb = float(a), float(b)
    except (TypeError, ValueError):
        return str(a).strip() == str(b).strip()
    if fb == 0:
        return fa == 0
    return abs(fa - fb) / max(abs(fb), 1e-9) <= tolerance


def _score_steps_completeness(
    extracted: dict[str, Any],
    expected: dict[str, Any],
) -> float:
    """Score how well extracted steps/instructions cover expected steps.

    Handles both a single 'instructions' string and a 'steps' list.
    Uses fuzzy sentence-level matching.
    """
    ext_steps = _get_step_sentences(extracted)
    exp_steps = _get_step_sentences(expected)

    if not exp_steps:
        return 1.0
    if not ext_steps:
        return 0.0

    found = 0
    for exp_sent in exp_steps:
        best = max((_fuzzy_ratio(exp_sent, ext_sent) for ext_sent in ext_steps), default=0.0)
        if best >= 0.6:
            found += 1

    return found / len(exp_steps)


def _get_step_sentences(data: dict[str, Any]) -> list[str]:
    """Extract a list of step sentences from instructions or steps field."""
    sentences: list[str] = []

    # Try structured steps first
    steps = data.get("steps") or []
    if steps and isinstance(steps, list):
        for step in steps:
            if isinstance(step, dict):
                text = step.get("instruction") or step.get("text") or ""
            else:
                text = str(step)
            text = text.strip()
            if text:
                sentences.append(text)
        return sentences

    # Fall back to instructions string
    instructions = data.get("instructions") or ""
    if not instructions:
        return []

    # Split on sentence-ending punctuation or numbered step markers
    parts = re.split(r"(?<=[.!?])\s+|\n+|\d+\.\s+", instructions)
    return [p.strip() for p in parts if p.strip() and len(p.strip()) > 10]


def _score_metadata_accuracy(
    extracted: dict[str, Any],
    expected: dict[str, Any],
) -> float:
    """Score metadata fields: title, prep_time, cook_time, servings."""
    checks: list[bool] = []

    # Title
    ext_title = _normalize_name(extracted.get("name"))
    exp_title = _normalize_name(expected.get("name"))
    if exp_title:
        checks.append(_fuzzy_ratio(ext_title, exp_title) >= 0.8)

    # Prep time
    if expected.get("prep_time_minutes") is not None:
        checks.append(
            _time_matches(extracted.get("prep_time_minutes"), expected["prep_time_minutes"])
        )

    # Cook time
    if expected.get("cook_time_minutes") is not None:
        checks.append(
            _time_matches(extracted.get("cook_time_minutes"), expected["cook_time_minutes"])
        )

    # Servings
    if expected.get("servings") is not None:
        checks.append(
            _int_matches(extracted.get("servings"), expected["servings"], tolerance=1)
        )

    if not checks:
        return 1.0
    return sum(1 for c in checks if c) / len(checks)


def _time_matches(
    actual: int | float | None,
    expected: int | float | None,
    tolerance: int = 5,
) -> bool:
    """Compare time values with tolerance in minutes."""
    if actual is None and expected is None:
        return True
    if actual is None or expected is None:
        return False
    try:
        return abs(int(actual) - int(expected)) <= tolerance
    except (TypeError, ValueError):
        return False


def _int_matches(
    actual: int | float | None,
    expected: int | float | None,
    tolerance: int = 0,
) -> bool:
    """Compare integer values with optional tolerance."""
    if actual is None and expected is None:
        return True
    if actual is None or expected is None:
        return False
    try:
        return abs(int(actual) - int(expected)) <= tolerance
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def score_extraction(extracted: dict[str, Any], expected: dict[str, Any]) -> dict[str, float]:
    """Score an extraction result against ground truth.

    Args:
        extracted: The recipe dict produced by an extractor.
        expected: The ground truth recipe dict.

    Returns:
        Dictionary with the following keys (all float 0-1):
        - ingredients_precision
        - ingredients_recall
        - amounts_accuracy
        - steps_completeness
        - metadata_accuracy
        - overall_f1  (weighted average of all scores)
    """
    ext_ingredients = extracted.get("ingredients", [])
    exp_ingredients = expected.get("ingredients", [])

    precision = _score_ingredients_precision(ext_ingredients, exp_ingredients)
    recall = _score_ingredients_recall(ext_ingredients, exp_ingredients)
    amounts = _score_amounts_accuracy(ext_ingredients, exp_ingredients)
    steps = _score_steps_completeness(extracted, expected)
    metadata = _score_metadata_accuracy(extracted, expected)

    # Weighted average — ingredients matter most, then steps, then metadata
    weights = {
        "ingredients_precision": 0.20,
        "ingredients_recall": 0.20,
        "amounts_accuracy": 0.15,
        "steps_completeness": 0.25,
        "metadata_accuracy": 0.20,
    }
    scores = {
        "ingredients_precision": precision,
        "ingredients_recall": recall,
        "amounts_accuracy": amounts,
        "steps_completeness": steps,
        "metadata_accuracy": metadata,
    }

    total_weight = sum(weights.values())
    overall = sum(scores[k] * weights[k] for k in weights) / total_weight

    scores["overall_f1"] = overall
    return scores
