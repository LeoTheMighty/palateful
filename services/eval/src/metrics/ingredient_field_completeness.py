"""eri-5 — per-field completeness metric for ingredient extraction.

For every ``(extracted, expected)`` recipe pair we walk the ingredients
list position-by-position and score each of the four structured fields
(``quantity``, ``unit``, ``name``, ``notes``) against ground truth.

Scoring:

* ``quantity`` — 1.0 when within ±5% of ground truth (tolerates
  0.333 vs 1/3 rounding); 0.0 otherwise. Null-vs-null counts as
  correct; null-vs-non-null is a miss; non-null-vs-null counts as
  hallucination (captured separately in ``ingredient_hallucination_rate``).
* ``unit`` / ``name`` / ``notes`` — 1.0 on case-insensitive exact
  match after strip; 0.0 otherwise. Same null semantics.

Denominator: the *extractable-field count* — fields the source
genuinely has (ground truth non-null) plus null-vs-null agreements
(which count as correct). A ground-truth-null field with an
extracted-non-null value scores 0 and is also tallied in the
hallucination sub-metric.

Aggregates:

* per-field mean (qty, unit, name, notes)
* per-extractor mean (keyed by the ``extractor_used`` field on the
  extracted recipe)
* overall mean across all fields + extractors
* ``ingredient_hallucination_rate`` — fraction of extracted ingredient
  fields that were non-null when ground truth was null

Target: overall ≥ 0.85. Soft gate in v1.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

_FIELDS: tuple[str, ...] = ("quantity", "unit", "name", "notes")
_QUANTITY_RELATIVE_TOLERANCE = 0.05


def _score_quantity(extracted: Any, expected: Any) -> float:
    if expected is None and extracted is None:
        return 1.0
    if expected is None or extracted is None:
        return 0.0
    try:
        ex = float(extracted)
        tg = float(expected)
    except (TypeError, ValueError):
        return 0.0
    if tg == 0:
        return 1.0 if ex == 0 else 0.0
    return 1.0 if abs(ex - tg) / abs(tg) <= _QUANTITY_RELATIVE_TOLERANCE else 0.0


def _score_text(extracted: Any, expected: Any) -> float:
    if expected is None and extracted is None:
        return 1.0
    if expected is None or extracted is None:
        return 0.0
    if not isinstance(extracted, str) or not isinstance(expected, str):
        return 0.0
    return 1.0 if extracted.strip().lower() == expected.strip().lower() else 0.0


def _score_field(field: str, extracted: Any, expected: Any) -> float:
    if field == "quantity":
        return _score_quantity(extracted, expected)
    return _score_text(extracted, expected)


def _is_hallucination(extracted: Any, expected: Any) -> bool:
    """Ground truth said null but the extractor filled in a value."""
    if expected is not None:
        return False
    if extracted is None:
        return False
    if isinstance(extracted, str) and not extracted.strip():
        return False
    return True


def compute_ingredient_field_completeness(
    pairs: Iterable[tuple[dict, dict]],
) -> dict[str, Any]:
    """Score ``(extracted, expected)`` recipe-dict pairs on the four
    structured ingredient fields.

    Each pair's ingredients lists are walked position-by-position up to
    the shorter length. Extractor length mismatches are not penalized
    here (that's covered by ``ingredient_count_accuracy``).

    ``extracted`` may carry an optional ``extractor_used`` key (set by
    ``ExtractionResult``); per-extractor means are reported when present.

    Returns:
        {
          "per_field": {field: {"score": float|None, "sample_count": int}},
          "per_extractor": {name: {"score": float|None, "sample_count": int}},
          "overall": float|None,  # mean of per-field means
          "sample_count": int,
          "ingredient_hallucination_rate": float|None,
        }
    """
    per_field_scores: dict[str, list[float]] = {f: [] for f in _FIELDS}
    per_extractor_scores: dict[str, list[float]] = {}
    hallucinations = 0
    hallucination_denominator = 0

    for extracted, expected in pairs:
        if not isinstance(extracted, dict) or not isinstance(expected, dict):
            continue
        ex_ings = extracted.get("ingredients") or []
        exp_ings = expected.get("ingredients") or []
        if not isinstance(ex_ings, list) or not isinstance(exp_ings, list):
            continue
        extractor = extracted.get("extractor_used") or "unknown"
        per_extractor_scores.setdefault(extractor, [])

        # Walk up to the shorter length — length mismatch is a separate
        # metric concern.
        limit = min(len(ex_ings), len(exp_ings))
        for i in range(limit):
            ex_ing = ex_ings[i] if isinstance(ex_ings[i], dict) else {}
            exp_ing = exp_ings[i] if isinstance(exp_ings[i], dict) else {}
            for field in _FIELDS:
                ex_val = ex_ing.get(field)
                exp_val = exp_ing.get(field)
                score = _score_field(field, ex_val, exp_val)
                per_field_scores[field].append(score)
                per_extractor_scores[extractor].append(score)

                # Hallucination tally
                hallucination_denominator += 1
                if _is_hallucination(ex_val, exp_val):
                    hallucinations += 1

    per_field_summary: dict[str, dict[str, Any]] = {}
    field_means: list[float] = []
    total_sample_count = 0
    for field in _FIELDS:
        scores = per_field_scores[field]
        total_sample_count += len(scores)
        if scores:
            mean = sum(scores) / len(scores)
            per_field_summary[field] = {"score": mean, "sample_count": len(scores)}
            field_means.append(mean)
        else:
            per_field_summary[field] = {"score": None, "sample_count": 0}

    per_extractor_summary: dict[str, dict[str, Any]] = {}
    for name, scores in per_extractor_scores.items():
        if scores:
            per_extractor_summary[name] = {
                "score": sum(scores) / len(scores),
                "sample_count": len(scores),
            }
        else:
            per_extractor_summary[name] = {"score": None, "sample_count": 0}

    overall = (sum(field_means) / len(field_means)) if field_means else None
    hallucination_rate = (
        hallucinations / hallucination_denominator
        if hallucination_denominator
        else None
    )

    return {
        "per_field": per_field_summary,
        "per_extractor": per_extractor_summary,
        "overall": overall,
        "sample_count": total_sample_count,
        "ingredient_hallucination_rate": hallucination_rate,
    }
