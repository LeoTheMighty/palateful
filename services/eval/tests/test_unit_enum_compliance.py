"""Tests for the riip-3 unit_enum_compliance metric."""

from __future__ import annotations

from src.metrics.unit_enum_compliance import compute_unit_enum_compliance


def test_all_canonical_yields_full_compliance():
    payload = {
        "recipes": [
            {
                "ingredients": [
                    {"unit": "tbsp"},
                    {"unit": "tsp"},
                    {"unit": "g"},
                ]
            }
        ]
    }
    out = compute_unit_enum_compliance(payload)
    assert out == {
        "compliance": 1.0,
        "total_units": 3,
        "compliant": 3,
        "non_compliant_breakdown": {},
    }


def test_partial_non_canonical_breakdown_named():
    payload = {
        "recipes": [
            {
                "ingredients": [
                    {"unit": "tbsp"},
                    {"unit": "tablespoon"},
                    {"unit": "teaspoon"},
                    {"unit": "tbsp"},
                ]
            }
        ]
    }
    out = compute_unit_enum_compliance(payload)
    assert out["total_units"] == 4
    assert out["compliant"] == 2
    assert out["compliance"] == 0.5
    assert out["non_compliant_breakdown"] == {"tablespoon": 1, "teaspoon": 1}


def test_null_and_empty_units_excluded_from_denominator():
    """null/empty are legitimate (count items, qualitative) — don't penalize."""
    payload = {
        "recipes": [
            {
                "ingredients": [
                    {"unit": None},
                    {"unit": ""},
                    {"unit": "   "},
                    {"unit": "tbsp"},
                ]
            }
        ]
    }
    out = compute_unit_enum_compliance(payload)
    assert out["total_units"] == 1
    assert out["compliant"] == 1
    assert out["compliance"] == 1.0


def test_case_and_whitespace_tolerant():
    payload = {
        "recipes": [
            {
                "ingredients": [
                    {"unit": " TBSP "},
                    {"unit": "Cup"},
                ]
            }
        ]
    }
    out = compute_unit_enum_compliance(payload)
    assert out["compliance"] == 1.0
    assert out["compliant"] == 2


def test_handles_legacy_single_recipe_shape():
    payload = {
        "ingredients": [
            {"unit": "tbsp"},
            {"unit": "tablespoons"},
        ]
    }
    out = compute_unit_enum_compliance(payload)
    assert out["total_units"] == 2
    assert out["compliant"] == 1
    assert out["non_compliant_breakdown"] == {"tablespoons": 1}


def test_empty_payload_returns_trivial_pass():
    assert compute_unit_enum_compliance({})["compliance"] == 1.0
    assert compute_unit_enum_compliance([])["compliance"] == 1.0


def test_skips_non_dict_ingredients_and_recipes():
    payload = {
        "recipes": [
            "not-a-dict",
            {"ingredients": ["loose-string", {"unit": "tbsp"}]},
        ]
    }
    out = compute_unit_enum_compliance(payload)
    assert out["compliant"] == 1
    assert out["total_units"] == 1
