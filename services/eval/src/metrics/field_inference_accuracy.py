"""efi-8 — per-field accuracy for extractor-inferred recipe fields.

For every (fixture × inferable-field) pair where:

1. The fixture's ground-truth has a value for that field, AND
2. The extractor marked the field in ``inferred_fields``,

we score how close the extractor's value landed to ground truth:

* Numeric fields (times, servings): 1.0 when within ±20% of ground truth;
  0.0 otherwise. Servings has a tolerance floor of ±1 since 20% of 4
  rounds to 0.
* Enum-ish fields (cuisine, category, primary_vibe, secondary_vibe): 1.0
  when case-insensitive exact match; 0.0 otherwise.
* Description: Levenshtein similarity on the first 200 characters. 1.0
  when ≥ 0.6 (the bar for "close enough"), otherwise the raw similarity
  ratio.

The overall score is the mean of per-field means. Soft gate: ≥ 0.6 —
reported only, never CI-blocking in v1.

``json_ld`` extractions always emit ``inferred_fields: []`` so they
contribute zero pairs and don't skew the overall score one way or the
other.
"""

from __future__ import annotations

from collections.abc import Iterable
from difflib import SequenceMatcher
from typing import Any

from utils.services.recipe_extractors.inference_prompt import INFERABLE_FIELDS

# Numeric fields get ±20% tolerance; servings also gets a ±1 floor so a
# 4-servings recipe doesn't need pixel-perfect agreement.
_NUMERIC_FIELDS: frozenset[str] = frozenset({
    "prep_time_minutes",
    "cook_time_minutes",
    "total_time_minutes",
    "servings",
})
_EXACT_MATCH_FIELDS: frozenset[str] = frozenset({
    "cuisine",
    "category",
    "primary_vibe",
    "secondary_vibe",
})
_DESCRIPTION_FIELD = "description"

_NUMERIC_RELATIVE_TOLERANCE = 0.20
_SERVINGS_FLOOR_TOLERANCE = 1
_DESCRIPTION_PREFIX_CHARS = 200
_DESCRIPTION_PASS_THRESHOLD = 0.6


def _score_numeric(field: str, extracted: Any, expected: Any) -> float | None:
    try:
        ex = float(extracted)
        tg = float(expected)
    except (TypeError, ValueError):
        return None
    if tg == 0:
        return 1.0 if ex == 0 else 0.0
    diff = abs(ex - tg)
    rel = diff / abs(tg)
    if rel <= _NUMERIC_RELATIVE_TOLERANCE:
        return 1.0
    if field == "servings" and diff <= _SERVINGS_FLOOR_TOLERANCE:
        return 1.0
    return 0.0


def _score_exact(extracted: Any, expected: Any) -> float | None:
    if not isinstance(extracted, str) or not isinstance(expected, str):
        return None
    return 1.0 if extracted.strip().lower() == expected.strip().lower() else 0.0


def _score_description(extracted: Any, expected: Any) -> float | None:
    if not isinstance(extracted, str) or not isinstance(expected, str):
        return None
    a = extracted[:_DESCRIPTION_PREFIX_CHARS]
    b = expected[:_DESCRIPTION_PREFIX_CHARS]
    ratio = SequenceMatcher(None, a, b).ratio()
    return 1.0 if ratio >= _DESCRIPTION_PASS_THRESHOLD else ratio


def _score_pair(field: str, extracted: Any, expected: Any) -> float | None:
    if field in _NUMERIC_FIELDS:
        return _score_numeric(field, extracted, expected)
    if field in _EXACT_MATCH_FIELDS:
        return _score_exact(extracted, expected)
    if field == _DESCRIPTION_FIELD:
        return _score_description(extracted, expected)
    return None


def compute_field_inference_accuracy(
    pairs: Iterable[tuple[dict, dict]],
) -> dict[str, Any]:
    """Score ``(extracted, expected)`` pairs across inferable fields.

    Each pair is a (extracted_recipe_dict, expected_recipe_dict) tuple.
    Pairs iterate over every fixture in the eval suite. The function
    derives per-field means over the pairs where BOTH (a) the extractor
    marked the field in ``inferred_fields`` and (b) the expected recipe
    has a non-null value.

    Returns:
        {
          "per_field": {field: {score, sample_count}},
          "overall": float,  # mean of per-field means (fields with
                             # 0 samples are excluded from the numerator)
          "sample_count": int,
        }
    """
    per_field_scores: dict[str, list[float]] = {f: [] for f in INFERABLE_FIELDS}

    for extracted, expected in pairs:
        if not isinstance(extracted, dict) or not isinstance(expected, dict):
            continue
        flagged = extracted.get("inferred_fields") or []
        if not isinstance(flagged, list):
            continue

        for field in flagged:
            if field not in INFERABLE_FIELDS:
                continue
            exp_val = expected.get(field)
            if exp_val is None:
                continue
            score = _score_pair(field, extracted.get(field), exp_val)
            if score is None:
                continue
            per_field_scores[field].append(score)

    per_field_summary: dict[str, dict[str, Any]] = {}
    totals: list[float] = []
    sample_count = 0
    for field in INFERABLE_FIELDS:
        scores = per_field_scores[field]
        sample_count += len(scores)
        if scores:
            mean = sum(scores) / len(scores)
            per_field_summary[field] = {
                "score": mean,
                "sample_count": len(scores),
            }
            totals.append(mean)
        else:
            per_field_summary[field] = {"score": None, "sample_count": 0}

    overall = (sum(totals) / len(totals)) if totals else None
    return {
        "per_field": per_field_summary,
        "overall": overall,
        "sample_count": sample_count,
    }
