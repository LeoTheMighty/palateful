"""Unit tests for ``apply_inference_penalty`` (efi-1).

Flat 0.05 per inferred field, capped at 5 fields (=0.25 max).
"""

from __future__ import annotations

import math

import pytest

from utils.services.recipe_extractors.confidence_heuristic import (
    apply_inference_penalty,
)


def test_no_inferred_is_no_op():
    assert apply_inference_penalty(0.72, 0) == pytest.approx(0.72)


def test_negative_inferred_is_no_op_and_clamps():
    assert apply_inference_penalty(0.5, -3) == pytest.approx(0.5)


def test_single_inferred_subtracts_0_05():
    assert apply_inference_penalty(0.8, 1) == pytest.approx(0.75)


def test_two_inferred_subtracts_0_10():
    assert apply_inference_penalty(0.7, 2) == pytest.approx(0.60)


def test_five_inferred_subtracts_0_25():
    assert apply_inference_penalty(0.9, 5) == pytest.approx(0.65)


def test_six_inferred_capped_at_0_25():
    assert apply_inference_penalty(0.9, 6) == pytest.approx(0.65)


def test_nine_inferred_capped_at_0_25():
    assert apply_inference_penalty(0.9, 9) == pytest.approx(0.65)


def test_clamps_to_zero_when_penalty_exceeds_score():
    # Score 0.10, penalty 0.25 → would go negative; clamp to 0.
    assert apply_inference_penalty(0.10, 5) == pytest.approx(0.0)


def test_clamps_to_one_when_input_above_one():
    assert apply_inference_penalty(1.5, 0) == pytest.approx(1.0)


def test_clamps_to_zero_when_input_below_zero():
    assert apply_inference_penalty(-0.2, 0) == pytest.approx(0.0)


def test_nan_coerces_to_zero():
    # NaN inputs must not leak into the result — downstream JSON /
    # Postgres serialization would break on a NaN confidence score.
    result = apply_inference_penalty(math.nan, 2)
    assert not math.isnan(result)
    assert result == pytest.approx(0.0)


def test_positive_infinity_coerces_and_penalizes_from_zero():
    result = apply_inference_penalty(math.inf, 2)
    assert not math.isinf(result)
    assert result == pytest.approx(0.0)


def test_negative_infinity_coerces_and_penalizes_from_zero():
    result = apply_inference_penalty(-math.inf, 2)
    assert not math.isinf(result)
    assert result == pytest.approx(0.0)


@pytest.mark.parametrize(
    "base,count,expected",
    [
        (0.72, 1, 0.67),
        (0.72, 2, 0.62),
        (0.72, 3, 0.57),
        (0.72, 4, 0.52),
        (0.72, 5, 0.47),
        (0.72, 7, 0.47),  # capped
    ],
)
def test_canonical_curve(base, count, expected):
    assert apply_inference_penalty(base, count) == pytest.approx(expected)
