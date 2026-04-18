"""Tests for the multi-recipe metrics + gate (bugs-imp-pho-5)."""

from src.config import EvalConfig, ThresholdConfig
from src.evaluators.recipe_extraction_evaluator import RecipeExtractionEvaluator
from src.runner import EvalRunner


def _make_evaluator() -> RecipeExtractionEvaluator:
    config = EvalConfig()
    return RecipeExtractionEvaluator(config)


# ---------- _normalize_to_recipe_list ----------


def test_normalize_multi_recipe_shape():
    evaluator = _make_evaluator()
    data = {"recipes": [{"name": "A"}, {"name": "B"}]}
    out = evaluator._normalize_to_recipe_list(data)
    assert [r["name"] for r in out] == ["A", "B"]


def test_normalize_bare_recipe_shape():
    evaluator = _make_evaluator()
    data = {"name": "Solo", "ingredients": []}
    out = evaluator._normalize_to_recipe_list(data)
    assert len(out) == 1
    assert out[0]["name"] == "Solo"


def test_normalize_empty_dict_returns_empty_list():
    """Empty or error dicts normalize to an empty list so len() comparisons
    stay meaningful (N=0 is a distinct grade from N=1)."""
    evaluator = _make_evaluator()
    assert evaluator._normalize_to_recipe_list({}) == []
    assert evaluator._normalize_to_recipe_list({"error": "nothing"}) == []


def test_normalize_drops_non_dict_entries():
    evaluator = _make_evaluator()
    data = {"recipes": [{"name": "A"}, "garbage", None, {"name": "B"}]}
    out = evaluator._normalize_to_recipe_list(data)
    assert [r["name"] for r in out] == ["A", "B"]


# ---------- recipe_count_accuracy ----------


def test_recipe_count_accuracy_exact_match():
    evaluator = _make_evaluator()
    expected = {"recipes": [{"name": "A", "ingredients": []}, {"name": "B", "ingredients": []}]}
    actual = {"recipes": [{"name": "A", "ingredients": []}, {"name": "B", "ingredients": []}]}
    m = evaluator._calculate_metrics(actual, expected)
    assert m["recipe_count_accuracy"] == 1.0
    assert m["expected_recipe_count"] == 2
    assert m["actual_recipe_count"] == 2


def test_recipe_count_accuracy_count_mismatch():
    evaluator = _make_evaluator()
    expected = {"recipes": [{"name": "A", "ingredients": []}, {"name": "B", "ingredients": []}]}
    actual = {"recipes": [{"name": "A", "ingredients": []}]}
    m = evaluator._calculate_metrics(actual, expected)
    assert m["recipe_count_accuracy"] == 0.0
    assert m["expected_recipe_count"] == 2
    assert m["actual_recipe_count"] == 1


def test_recipe_count_accuracy_mixed_shapes():
    """Bare single-recipe expected + multi-recipe actual → count mismatch."""
    evaluator = _make_evaluator()
    expected = {"name": "A", "ingredients": []}
    actual = {"recipes": [{"name": "A", "ingredients": []}, {"name": "B", "ingredients": []}]}
    m = evaluator._calculate_metrics(actual, expected)
    assert m["expected_recipe_count"] == 1
    assert m["actual_recipe_count"] == 2
    assert m["recipe_count_accuracy"] == 0.0


# ---------- field metrics under count mismatch ----------


def test_unpaired_expected_recipe_pulls_field_accuracy_down():
    """Missing a recipe: paired recipe scores + one 0 for the missed one,
    averaged across total_pairs."""
    evaluator = _make_evaluator()
    expected = {
        "recipes": [
            {"name": "A", "ingredients": [], "instructions": "x"},
            {"name": "B", "ingredients": [], "instructions": "y"},
        ]
    }
    actual = {
        "recipes": [
            {"name": "A", "ingredients": [], "instructions": "x"},
        ]
    }
    m = evaluator._calculate_metrics(actual, expected)
    # 1 paired (identical) + 1 unpaired → numerator from 1 pair / 2 total
    assert m["field_accuracy"] < 1.0
    assert m["field_accuracy"] > 0.0


def test_legacy_single_recipe_still_grades():
    """The single-recipe path still produces a meaningful field_accuracy."""
    evaluator = _make_evaluator()
    expected = {
        "name": "Cookies",
        "ingredients": [{"text": "flour"}],
        "instructions": "Mix and bake.",
    }
    actual = {
        "name": "Cookies",
        "ingredients": [{"text": "flour"}],
        "instructions": "Mix and bake.",
    }
    m = evaluator._calculate_metrics(actual, expected)
    assert m["recipe_count_accuracy"] == 1.0
    assert m["field_accuracy"] >= 0.9


# ---------- runner threshold gate ----------


def test_runner_gate_blocks_on_recipe_count_accuracy():
    """With a full field_accuracy but low recipe_count_accuracy, the
    suite fails the gate."""
    config = EvalConfig(thresholds=ThresholdConfig(
        recipe_field_accuracy=0.9,
        recipe_count_accuracy=0.8,
    ))
    runner = EvalRunner(config)
    # Simulate 2/3 cases got the count wrong → avg 0.33, below 0.8
    metrics = {
        "field_accuracy_avg": 0.95,
        "recipe_count_accuracy_avg": 0.333,
    }
    assert runner._check_thresholds("recipe_extraction", metrics) is False


def test_runner_gate_blocks_on_field_accuracy():
    """field_accuracy below threshold still fails even if count is perfect."""
    config = EvalConfig(thresholds=ThresholdConfig(
        recipe_field_accuracy=0.9,
        recipe_count_accuracy=0.8,
    ))
    runner = EvalRunner(config)
    metrics = {
        "field_accuracy_avg": 0.5,
        "recipe_count_accuracy_avg": 1.0,
    }
    assert runner._check_thresholds("recipe_extraction", metrics) is False


def test_runner_gate_passes_when_both_above_threshold():
    config = EvalConfig(thresholds=ThresholdConfig(
        recipe_field_accuracy=0.9,
        recipe_count_accuracy=0.8,
    ))
    runner = EvalRunner(config)
    metrics = {
        "field_accuracy_avg": 0.95,
        "recipe_count_accuracy_avg": 0.9,
    }
    assert runner._check_thresholds("recipe_extraction", metrics) is True


def test_runner_gate_treats_missing_count_metric_as_1():
    """Legacy runs without multi-recipe fixtures should not be penalized."""
    config = EvalConfig(thresholds=ThresholdConfig(
        recipe_field_accuracy=0.9,
        recipe_count_accuracy=0.8,
    ))
    runner = EvalRunner(config)
    metrics = {
        "field_accuracy_avg": 0.95,
        # No recipe_count_accuracy_avg key
    }
    assert runner._check_thresholds("recipe_extraction", metrics) is True
