"""eri-5 — tests for the ingredient_field_completeness metric + the
7 ingredient-fidelity fixtures under
``services/eval/fixtures/ingredient_fidelity/``.

These are pure-Python unit tests. They do NOT hit OpenAI. The "eval" in
this story is the metric function + fixture coverage — the real
end-to-end eval run is gated on the rollout runbook (eri-6) and will
be wired in once flags are on in prod.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from src.metrics.ingredient_field_completeness import (
    compute_ingredient_field_completeness,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE_DIR = _REPO_ROOT / "services/eval/fixtures/ingredient_fidelity"
_BASELINE_PATH = (
    _REPO_ROOT / "services/eval/baselines/ingredient_field_completeness_baseline.json"
)

# The 7 fixtures the epic specifies (3 happy + 4 negative).
_EXPECTED_FIXTURE_NAMES = {
    "1_clove_garlic_jsonld.yaml",
    "300_gram_vinegar_jsonld.yaml",
    "2_stalks_celery_text.yaml",
    "no_notes_simple_text.yaml",
    "pinchful_substring_text.yaml",
    "range_quantity_jsonld.yaml",
    "mixed_structure_jsonld.yaml",
}


def _load_fixture(name: str) -> dict:
    return yaml.safe_load((_FIXTURE_DIR / name).read_text())


# ---------------------------------------------------------------------------
# Fixture coverage + shape
# ---------------------------------------------------------------------------


def test_exactly_seven_ingredient_fidelity_fixtures_exist():
    names = {p.name for p in _FIXTURE_DIR.glob("*.yaml")}
    assert names == _EXPECTED_FIXTURE_NAMES, (
        f"Missing: {_EXPECTED_FIXTURE_NAMES - names}, "
        f"Unexpected: {names - _EXPECTED_FIXTURE_NAMES}"
    )


def test_every_fixture_has_source_type_and_expected_ingredients():
    for name in _EXPECTED_FIXTURE_NAMES:
        fixture = _load_fixture(name)
        assert fixture.get("source_type") in {"jsonld", "text", "image"}, name
        assert isinstance(fixture.get("expected", {}).get("ingredients"), list), name


def test_every_expected_ingredient_has_all_four_fields():
    """Ground-truth rows MUST explicitly set all four scorable fields
    (quantity/unit/name/notes) — even if null — so the metric's
    null-vs-null accounting has consistent input."""
    required = {"quantity", "unit", "name", "notes"}
    for name in _EXPECTED_FIXTURE_NAMES:
        fixture = _load_fixture(name)
        for ing in fixture["expected"]["ingredients"]:
            missing = required - set(ing.keys())
            assert not missing, f"{name}: ingredient missing fields {missing}: {ing}"


# ---------------------------------------------------------------------------
# Metric behavior — perfect extraction scores 1.0
# ---------------------------------------------------------------------------


def test_perfect_extraction_scores_one():
    """Ground-truth == extracted → overall 1.0, all fields 1.0, zero hallucinations."""
    for name in _EXPECTED_FIXTURE_NAMES:
        fixture = _load_fixture(name)
        expected = fixture["expected"]
        # Mirror the expected ingredients as the "extracted" payload.
        extracted = {"extractor_used": "json_ld_parse_pass", "ingredients": expected["ingredients"]}
        out = compute_ingredient_field_completeness([(extracted, expected)])
        assert out["overall"] == 1.0, f"{name}: expected overall=1.0, got {out['overall']}"
        assert out["ingredient_hallucination_rate"] == 0.0, name
        for field in ("quantity", "unit", "name", "notes"):
            assert out["per_field"][field]["score"] == 1.0, f"{name}: {field}"


# ---------------------------------------------------------------------------
# Metric behavior — per-field scoring
# ---------------------------------------------------------------------------


def test_quantity_within_five_percent_scores_one():
    expected = {"ingredients": [{"quantity": 100, "unit": "g", "name": "flour", "notes": None}]}
    extracted = {
        "ingredients": [{"quantity": 104.5, "unit": "g", "name": "flour", "notes": None}]
    }
    out = compute_ingredient_field_completeness([(extracted, expected)])
    assert out["per_field"]["quantity"]["score"] == 1.0


def test_quantity_outside_five_percent_scores_zero():
    expected = {"ingredients": [{"quantity": 100, "unit": "g", "name": "flour", "notes": None}]}
    extracted = {
        "ingredients": [{"quantity": 110, "unit": "g", "name": "flour", "notes": None}]
    }
    out = compute_ingredient_field_completeness([(extracted, expected)])
    assert out["per_field"]["quantity"]["score"] == 0.0


def test_null_vs_null_quantity_counts_as_correct():
    expected = {"ingredients": [{"quantity": None, "unit": None, "name": "salt", "notes": "to taste"}]}
    extracted = {
        "ingredients": [
            {"quantity": None, "unit": None, "name": "salt", "notes": "to taste"}
        ]
    }
    out = compute_ingredient_field_completeness([(extracted, expected)])
    assert out["overall"] == 1.0


def test_hallucinated_notes_score_zero_and_tally_hallucination():
    """Ground truth: notes=null. Extractor filled in "sifted". Score 0 +
    hallucination bump."""
    expected = {"ingredients": [{"quantity": 2, "unit": "cup", "name": "flour", "notes": None}]}
    extracted = {
        "ingredients": [{"quantity": 2, "unit": "cup", "name": "flour", "notes": "sifted"}]
    }
    out = compute_ingredient_field_completeness([(extracted, expected)])
    assert out["per_field"]["notes"]["score"] == 0.0
    # 1 hallucination out of 4 field slots
    assert out["ingredient_hallucination_rate"] == 0.25


def test_unit_case_insensitive_match():
    expected = {"ingredients": [{"quantity": 1, "unit": "cup", "name": "water", "notes": None}]}
    extracted = {
        "ingredients": [{"quantity": 1, "unit": "CUP", "name": "water", "notes": None}]
    }
    out = compute_ingredient_field_completeness([(extracted, expected)])
    assert out["per_field"]["unit"]["score"] == 1.0


def test_name_mismatch_scores_zero():
    expected = {"ingredients": [{"quantity": 1, "unit": "cup", "name": "water", "notes": None}]}
    extracted = {
        "ingredients": [{"quantity": 1, "unit": "cup", "name": "milk", "notes": None}]
    }
    out = compute_ingredient_field_completeness([(extracted, expected)])
    assert out["per_field"]["name"]["score"] == 0.0


def test_per_extractor_means_aggregate_correctly():
    expected = {"ingredients": [{"quantity": 1, "unit": "cup", "name": "water", "notes": None}]}
    extracted_ok = {
        "extractor_used": "json_ld_parse_pass",
        "ingredients": [{"quantity": 1, "unit": "cup", "name": "water", "notes": None}],
    }
    extracted_bad = {
        "extractor_used": "ai",
        "ingredients": [{"quantity": 2, "unit": "ml", "name": "juice", "notes": "x"}],
    }
    out = compute_ingredient_field_completeness(
        [(extracted_ok, expected), (extracted_bad, expected)]
    )
    assert out["per_extractor"]["json_ld_parse_pass"]["score"] == 1.0
    # ai extractor got all 4 fields wrong (qty, unit, name + hallucinated notes)
    assert out["per_extractor"]["ai"]["score"] == 0.0


def test_empty_pairs_returns_nulls():
    out = compute_ingredient_field_completeness([])
    assert out["overall"] is None
    assert out["sample_count"] == 0
    assert out["ingredient_hallucination_rate"] is None
    for field in ("quantity", "unit", "name", "notes"):
        assert out["per_field"][field]["score"] is None
        assert out["per_field"][field]["sample_count"] == 0


# ---------------------------------------------------------------------------
# Baseline shape
# ---------------------------------------------------------------------------


def test_baseline_file_exists_and_is_valid_json():
    import json

    data = json.loads(_BASELINE_PATH.read_text())
    # Top-level keys from the eri-5 spec
    assert "ingredient_field_completeness" in data
    assert "ingredient_hallucination_rate" in data
    assert "thresholds" in data
    # Soft gate in v1
    assert data["thresholds"]["_enforcement"] == "soft"
    # Thresholds match the epic's DoD
    assert data["thresholds"]["ingredient_field_completeness_overall_min"] == 0.85


# ---------------------------------------------------------------------------
# Eval-config registration
# ---------------------------------------------------------------------------


def test_eval_config_registers_ingredient_fidelity_suite():
    config = yaml.safe_load(
        (_REPO_ROOT / "services/eval/eval.config.yaml").read_text()
    )
    suite = config["metrics"].get("ingredient_fidelity")
    assert suite == [
        "ingredient_field_completeness",
        "ingredient_hallucination_rate",
    ]
    # Thresholds are present but soft-gated.
    thresholds = config["thresholds"]
    assert thresholds["ingredient_field_completeness_min"] == 0.85
    assert thresholds["ingredient_hallucination_rate_max"] == 0.10
