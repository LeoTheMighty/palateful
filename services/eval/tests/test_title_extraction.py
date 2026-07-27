"""irrd-3a — unit tests for title_extraction_f1 + the AC11 regression gate.

Deterministic only: pure arithmetic over hand-built titles, no network
and no OPENAI_API_KEY. The expensive real-LLM run that *produces* the
extractions is opt-in and lives outside pytest.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.metrics.title_extraction import (
    TITLE_REGRESSION_MAX_RELATIVE_DROP,
    TitleSample,
    baseline_title_f1,
    check_title_regression_gate,
    compute_title_extraction_f1,
    format_title_regression_summary,
)

BASELINE_PATH = (
    Path(__file__).resolve().parents[1] / "baselines" / "extraction_baseline.json"
)


def _sample(fixture_id: str, got: str | None, want: str) -> TitleSample:
    return TitleSample(fixture_id=fixture_id, extracted_title=got, expected_title=want)


# -------------------------------------------------------------------
# Token F1 math
# -------------------------------------------------------------------


def test_identical_titles_score_one():
    out = compute_title_extraction_f1([
        _sample("a", "Simple Garlic Butter Pasta", "Simple Garlic Butter Pasta"),
    ])
    assert out["title_extraction_f1"] == 1.0
    assert out["precision"] == 1.0
    assert out["recall"] == 1.0
    assert out["exact_match_rate"] == 1.0


def test_match_is_case_and_punctuation_insensitive():
    out = compute_title_extraction_f1([
        _sample("a", "GARLIC-BUTTER PASTA!", "Garlic Butter Pasta"),
    ])
    assert out["title_extraction_f1"] == 1.0
    assert out["exact_match_rate"] == 1.0


def test_extra_whitespace_does_not_change_score():
    out = compute_title_extraction_f1([
        _sample("a", "  Banana   Bread\n", "Banana Bread"),
    ])
    assert out["title_extraction_f1"] == 1.0


def test_missing_token_costs_recall_not_precision():
    # got 2 of 3 tokens, no spurious tokens
    out = compute_title_extraction_f1([
        _sample("a", "Garlic Pasta", "Simple Garlic Pasta"),
    ])
    row = out["per_fixture"][0]
    assert row["precision"] == 1.0
    assert abs(row["recall"] - 2 / 3) < 1e-9
    assert abs(row["f1"] - 0.8) < 1e-9
    assert row["exact_match"] is False


def test_extra_token_costs_precision_not_recall():
    out = compute_title_extraction_f1([
        _sample("a", "Best Ever Banana Bread", "Banana Bread"),
    ])
    row = out["per_fixture"][0]
    assert row["precision"] == 0.5
    assert row["recall"] == 1.0
    assert abs(row["f1"] - 2 / 3) < 1e-9


def test_completely_wrong_title_scores_zero():
    out = compute_title_extraction_f1([_sample("a", "Beef Stew", "Banana Bread")])
    assert out["title_extraction_f1"] == 0.0


def test_missing_extracted_title_scores_zero_not_skipped():
    out = compute_title_extraction_f1([_sample("a", None, "Banana Bread")])
    assert out["title_extraction_f1"] == 0.0
    assert out["sample_count"] == 1
    assert out["skipped_count"] == 0


def test_blank_extracted_title_scores_zero():
    out = compute_title_extraction_f1([_sample("a", "   ", "Banana Bread")])
    assert out["title_extraction_f1"] == 0.0


def test_repeated_token_overlap_is_multiset_bounded():
    # "chocolate" appears twice in the guess but once in truth — the
    # second occurrence must not earn credit.
    out = compute_title_extraction_f1([
        _sample("a", "Chocolate Chocolate Cake", "Chocolate Cake"),
    ])
    row = out["per_fixture"][0]
    assert abs(row["precision"] - 2 / 3) < 1e-9
    assert row["recall"] == 1.0


def test_headline_metric_is_mean_of_per_fixture_f1():
    out = compute_title_extraction_f1([
        _sample("a", "Banana Bread", "Banana Bread"),  # 1.0
        _sample("b", "Beef Stew", "Banana Bread"),  # 0.0
    ])
    assert out["title_extraction_f1"] == 0.5
    assert out["exact_match_rate"] == 0.5
    assert out["sample_count"] == 2


def test_unicode_titles_tokenize_as_words():
    out = compute_title_extraction_f1([
        _sample("a", "Crème Brûlée", "Creme Brulee"),
    ])
    # Accents differ, so the tokens differ — the point is that the words
    # stay whole rather than shattering into single letters.
    row = out["per_fixture"][0]
    assert row["f1"] == 0.0
    assert compute_title_extraction_f1(
        [_sample("b", "Crème Brûlée", "Crème Brûlée")]
    )["title_extraction_f1"] == 1.0


# -------------------------------------------------------------------
# Input coercion
# -------------------------------------------------------------------


def test_accepts_recipe_dict_pairs_keyed_on_name():
    out = compute_title_extraction_f1([
        ({"name": "Banana Bread"}, {"name": "Banana Bread"}),
    ])
    assert out["title_extraction_f1"] == 1.0
    assert out["per_fixture"][0]["fixture_id"] == "unknown"


def test_accepts_title_key_as_well_as_name():
    out = compute_title_extraction_f1([
        ({"title": "Banana Bread"}, {"name": "Banana Bread"}),
    ])
    assert out["title_extraction_f1"] == 1.0


def test_accepts_triples_carrying_the_fixture_id():
    out = compute_title_extraction_f1([
        ("banana_bread", {"name": "Banana Bread"}, {"name": "Banana Bread"}),
    ])
    assert out["per_fixture"][0]["fixture_id"] == "banana_bread"


def test_accepts_runner_style_dicts():
    out = compute_title_extraction_f1([
        {
            "id": "simple_pasta",
            "extracted": {"name": "Garlic Pasta"},
            "expected": {"name": "Garlic Pasta"},
        },
    ])
    assert out["per_fixture"][0]["fixture_id"] == "simple_pasta"
    assert out["title_extraction_f1"] == 1.0


def test_fixture_without_ground_truth_title_is_skipped_not_zeroed():
    out = compute_title_extraction_f1([
        _sample("a", "Banana Bread", "Banana Bread"),
        ({"name": "Whatever"}, {"servings": 4}),
    ])
    assert out["title_extraction_f1"] == 1.0
    assert out["sample_count"] == 1
    assert out["skipped_count"] == 1


def test_malformed_entries_are_skipped():
    out = compute_title_extraction_f1(["nonsense", 42, None])
    assert out["sample_count"] == 0
    assert out["skipped_count"] == 3


def test_empty_run_reports_none_not_zero():
    out = compute_title_extraction_f1([])
    assert out["title_extraction_f1"] is None
    assert out["precision"] is None
    assert out["exact_match_rate"] is None
    assert out["sample_count"] == 0
    assert out["per_fixture"] == []


def test_worst_offenders_are_ranked_ascending_by_f1():
    out = compute_title_extraction_f1([
        _sample("good", "Banana Bread", "Banana Bread"),
        _sample("bad", "Beef Stew", "Banana Bread"),
        _sample("mid", "Bread", "Banana Bread"),
    ])
    ids = [row["fixture_id"] for row in out["worst_offenders"]]
    assert ids[0] == "bad"
    assert ids[1] == "mid"


# -------------------------------------------------------------------
# Regression gate
# -------------------------------------------------------------------


def test_gate_passes_when_metric_holds_steady():
    gate = check_title_regression_gate(
        {"title_extraction_f1": 0.90, "sample_count": 8},
        {"title_extraction": {"title_extraction_f1": 0.90}},
    )
    assert gate["passed"] is True
    assert gate["relative_drop"] == 0.0
    assert abs(gate["min_allowed"] - 0.855) < 1e-9


def test_gate_passes_on_improvement():
    gate = check_title_regression_gate(
        {"title_extraction_f1": 0.95, "sample_count": 8},
        {"title_extraction": {"title_extraction_f1": 0.90}},
    )
    assert gate["passed"] is True
    assert gate["relative_drop"] < 0


def test_gate_passes_at_exactly_five_percent_drop():
    gate = check_title_regression_gate(
        {"title_extraction_f1": 0.90 * 0.95, "sample_count": 8},
        {"title_extraction": {"title_extraction_f1": 0.90}},
    )
    assert gate["passed"] is True
    assert abs(gate["relative_drop"] - 0.05) < 1e-9


def test_gate_fails_just_past_five_percent_drop():
    gate = check_title_regression_gate(
        {"title_extraction_f1": 0.90 * 0.95 - 0.001, "sample_count": 8},
        {"title_extraction": {"title_extraction_f1": 0.90}},
    )
    assert gate["passed"] is False
    assert gate["relative_drop"] > 0.05
    assert "retune" in gate["reason"]


def test_gate_is_relative_not_absolute():
    # A low-but-stable baseline must not fail just for being low.
    gate = check_title_regression_gate(
        {"title_extraction_f1": 0.40, "sample_count": 8},
        {"title_extraction": {"title_extraction_f1": 0.40}},
    )
    assert gate["passed"] is True


def test_gate_passes_and_flags_when_baseline_is_the_null_placeholder():
    gate = check_title_regression_gate(
        {"title_extraction_f1": 0.88, "sample_count": 8},
        {"title_extraction": {"title_extraction_f1": None}},
    )
    assert gate["passed"] is True
    assert gate["baseline_missing"] is True
    assert gate["min_allowed"] is None
    assert "no baseline" in gate["reason"]


def test_gate_passes_when_no_baseline_argument_given():
    gate = check_title_regression_gate({"title_extraction_f1": 0.88, "sample_count": 8})
    assert gate["passed"] is True
    assert gate["baseline_missing"] is True


def test_gate_fails_closed_on_empty_run():
    gate = check_title_regression_gate(
        compute_title_extraction_f1([]),
        {"title_extraction": {"title_extraction_f1": 0.90}},
    )
    assert gate["passed"] is False
    assert gate["value"] is None
    assert "refusing to pass" in gate["reason"]


def test_gate_fails_closed_on_empty_run_even_without_baseline():
    gate = check_title_regression_gate(compute_title_extraction_f1([]))
    assert gate["passed"] is False
    assert gate["baseline_missing"] is True


def test_zero_baseline_cannot_be_regressed_against():
    gate = check_title_regression_gate(
        {"title_extraction_f1": 0.0, "sample_count": 8},
        {"title_extraction": {"title_extraction_f1": 0.0}},
    )
    assert gate["passed"] is True
    assert gate["relative_drop"] == 0.0


def test_gate_honours_a_custom_drop_tolerance():
    gate = check_title_regression_gate(
        {"title_extraction_f1": 0.80, "sample_count": 8},
        {"title_extraction": {"title_extraction_f1": 0.90}},
        max_relative_drop=0.20,
    )
    assert gate["passed"] is True
    assert gate["max_relative_drop"] == 0.20


def test_gate_reports_soft_enforcement():
    gate = check_title_regression_gate(
        {"title_extraction_f1": 0.90, "sample_count": 8},
        {"title_extraction": {"title_extraction_f1": 0.90}},
    )
    assert gate["enforcement"] == "soft"
    assert gate["metric"] == "title_extraction_f1"


# -------------------------------------------------------------------
# Baseline payload handling
# -------------------------------------------------------------------


def test_baseline_reader_accepts_the_bare_shape():
    assert baseline_title_f1({"title_extraction_f1": 0.75}) == 0.75


def test_baseline_reader_rejects_non_numeric_and_booleans():
    assert baseline_title_f1({"title_extraction_f1": "0.9"}) == 0.9
    assert baseline_title_f1({"title_extraction_f1": True}) is None
    assert baseline_title_f1({"title_extraction_f1": float("nan")}) is None
    assert baseline_title_f1(None) is None
    assert baseline_title_f1({}) is None


# -------------------------------------------------------------------
# Summary rendering
# -------------------------------------------------------------------


def test_summary_carries_value_baseline_and_threshold():
    result = compute_title_extraction_f1([
        _sample("banana_bread", "Beef Stew", "Banana Bread"),
    ])
    gate = check_title_regression_gate(
        result, {"title_extraction": {"title_extraction_f1": 0.90}}
    )
    text = format_title_regression_summary(result, gate)
    assert "FAILED" in text
    assert "0.0000" in text  # metric value
    assert "0.9000" in text  # baseline
    assert "5%" in text  # threshold
    assert "banana_bread" in text  # worst offender named


def test_summary_hides_worst_offenders_when_passing():
    result = compute_title_extraction_f1([
        _sample("banana_bread", "Banana Bread", "Banana Bread"),
    ])
    gate = check_title_regression_gate(
        result, {"title_extraction": {"title_extraction_f1": 0.90}}
    )
    text = format_title_regression_summary(result, gate)
    assert "PASSED" in text
    assert "worst fixtures" not in text


def test_summary_survives_the_null_placeholder_baseline():
    result = compute_title_extraction_f1([_sample("a", "Banana Bread", "Banana Bread")])
    gate = check_title_regression_gate(result, json.loads(BASELINE_PATH.read_text()))
    text = format_title_regression_summary(result, gate)
    assert "PASSED" in text
    assert "n/a" in text  # baseline + min_allowed render as n/a


def test_summary_reports_skipped_fixtures():
    result = compute_title_extraction_f1([
        _sample("a", "Banana Bread", "Banana Bread"),
        ({"name": "x"}, {}),
    ])
    gate = check_title_regression_gate(result)
    assert "1 skipped" in format_title_regression_summary(result, gate)


# -------------------------------------------------------------------
# Drift guards — checked-in baseline vs the module's constants
# -------------------------------------------------------------------


def test_checked_in_baseline_exists_and_is_valid_json():
    assert BASELINE_PATH.is_file()
    json.loads(BASELINE_PATH.read_text())


def test_baseline_threshold_matches_the_module_constant():
    baseline = json.loads(BASELINE_PATH.read_text())
    assert (
        baseline["thresholds"]["title_extraction_f1_max_relative_drop"]
        == TITLE_REGRESSION_MAX_RELATIVE_DROP
    )


def test_baseline_ships_null_placeholders_until_the_first_real_run():
    baseline = json.loads(BASELINE_PATH.read_text())
    assert baseline["title_extraction"]["title_extraction_f1"] is None
    assert baseline["_generated_at"] is None
    assert baseline_title_f1(baseline) is None


def test_baseline_records_the_fixture_set_the_gate_runs_against():
    baseline = json.loads(BASELINE_PATH.read_text())
    assert baseline["_fixture_set"] == "services/eval/fixtures/expected/*.json"


def test_every_checked_in_fixture_has_a_ground_truth_title():
    # The gate's denominator is fixtures with an expected title; a
    # fixture missing one silently shrinks the sample and makes runs
    # non-comparable.
    fixtures_dir = BASELINE_PATH.parents[1] / "fixtures" / "expected"
    files = sorted(fixtures_dir.glob("*.json"))
    assert files, "no expected fixtures found"
    for path in files:
        data = json.loads(path.read_text())
        recipes = data["recipes"] if isinstance(data.get("recipes"), list) else [data]
        for recipe in recipes:
            assert (recipe.get("name") or recipe.get("title") or "").strip(), (
                f"{path.name} has a recipe with no ground-truth title"
            )
