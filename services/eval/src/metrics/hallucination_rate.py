"""efi-8 — anti-metric: how often the extractor guessed when the source had the answer.

The "hallucination" this metric tracks is narrow: for every
(fixture × inferable-field) pair where BOTH the ground truth has a
value AND the extractor marked the field as inferred, we count that as
a hallucination. The extractor "guessed" even though the source
explicitly stated the value — a measurable bad behavior.

rate = hallucinations / (extractable_field × fixture_count)

where ``extractable_field × fixture_count`` is the denominator of
(fixture, field) pairs where ground truth HAS a value (the subset of
pairs where the extractor even had a chance to hallucinate). Pairs with
no ground-truth value for a field are out of scope — we can't say the
extractor was wrong to guess when the source actually lacked the field.

Soft gate: ≤ 0.15 — reported only, never CI-blocking in v1.

``json_ld`` always emits ``inferred_fields: []`` so its contribution to
the numerator is zero. When the runner per-extractor breaks out the
metric, json_ld's rate is always 0.0 by construction — exclude it from
any per-extractor ranking to avoid gaming.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from utils.services.recipe_extractors.inference_prompt import INFERABLE_FIELDS


def compute_hallucination_rate(
    pairs: Iterable[tuple[dict, dict]],
) -> dict[str, Any]:
    """Compute the hallucination rate across ``(extracted, expected)`` pairs.

    Returns:
        {
          "rate": float,                  # hallucinations / extractable_pairs
          "hallucinations": int,          # num (fixture, field) guesses
          "extractable_pairs": int,       # num (fixture, field) where gt exists
          "per_field": {field: {rate, hallucinations, extractable}},
        }
    """
    total_hallucinations = 0
    total_extractable = 0
    per_field: dict[str, dict[str, int]] = {
        f: {"hallucinations": 0, "extractable": 0} for f in INFERABLE_FIELDS
    }

    for extracted, expected in pairs:
        if not isinstance(extracted, dict) or not isinstance(expected, dict):
            continue
        flagged_raw = extracted.get("inferred_fields") or []
        flagged = (
            set(f for f in flagged_raw if isinstance(f, str))
            if isinstance(flagged_raw, list)
            else set()
        )

        for field in INFERABLE_FIELDS:
            exp_val = expected.get(field)
            if exp_val is None:
                continue
            # Empty-string / whitespace-only is treated as "no ground
            # truth" — the source didn't really provide the field.
            if isinstance(exp_val, str) and not exp_val.strip():
                continue
            per_field[field]["extractable"] += 1
            total_extractable += 1
            if field in flagged:
                per_field[field]["hallucinations"] += 1
                total_hallucinations += 1

    per_field_out: dict[str, dict[str, Any]] = {}
    for field, counts in per_field.items():
        hall = counts["hallucinations"]
        ex = counts["extractable"]
        rate = (hall / ex) if ex else 0.0
        per_field_out[field] = {
            "rate": rate,
            "hallucinations": hall,
            "extractable": ex,
        }

    overall_rate = (
        total_hallucinations / total_extractable
        if total_extractable
        else 0.0
    )

    return {
        "rate": overall_rate,
        "hallucinations": total_hallucinations,
        "extractable_pairs": total_extractable,
        "per_field": per_field_out,
    }
