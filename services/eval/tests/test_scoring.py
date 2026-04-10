"""Tests for the scoring module."""

import pytest

from src.scoring import (
    _fuzzy_ratio,
    _match_ingredients,
    _normalize_unit,
    _quantities_match,
    _score_amounts_accuracy,
    _score_ingredients_precision,
    _score_ingredients_recall,
    _score_metadata_accuracy,
    _score_steps_completeness,
    score_extraction,
)


# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------


class TestNormalizeUnit:
    def test_singular(self):
        assert _normalize_unit("cups") == "cup"
        assert _normalize_unit("tablespoons") == "tablespoon"
        assert _normalize_unit("teaspoons") == "teaspoon"

    def test_abbreviations(self):
        assert _normalize_unit("tbsp") == "tablespoon"
        assert _normalize_unit("tsp") == "teaspoon"
        assert _normalize_unit("oz") == "ounce"
        assert _normalize_unit("lb") == "pound"
        assert _normalize_unit("g") == "gram"

    def test_none(self):
        assert _normalize_unit(None) == ""

    def test_already_normalized(self):
        assert _normalize_unit("cup") == "cup"


class TestQuantitiesMatch:
    def test_exact(self):
        assert _quantities_match(2.0, 2.0)

    def test_both_none(self):
        assert _quantities_match(None, None)

    def test_one_none(self):
        assert not _quantities_match(None, 2.0)
        assert not _quantities_match(2.0, None)

    def test_close_enough(self):
        assert _quantities_match(2.0, 2.0)

    def test_string_match(self):
        assert _quantities_match("2", "2")

    def test_mismatch(self):
        assert not _quantities_match(1.0, 2.0)


class TestFuzzyRatio:
    def test_identical(self):
        assert _fuzzy_ratio("flour", "flour") == 1.0

    def test_similar(self):
        assert _fuzzy_ratio("all-purpose flour", "all purpose flour") > 0.9

    def test_different(self):
        assert _fuzzy_ratio("flour", "sugar") < 0.5


# ---------------------------------------------------------------------------
# Ingredient matching
# ---------------------------------------------------------------------------


class TestMatchIngredients:
    def test_exact_match(self):
        extracted = [{"name": "flour"}, {"name": "sugar"}]
        expected = [{"name": "flour"}, {"name": "sugar"}]
        matched, unmatched_ext, unmatched_exp = _match_ingredients(extracted, expected)
        assert len(matched) == 2
        assert len(unmatched_ext) == 0
        assert len(unmatched_exp) == 0

    def test_partial_match(self):
        extracted = [{"name": "flour"}, {"name": "butter"}]
        expected = [{"name": "flour"}, {"name": "sugar"}]
        matched, unmatched_ext, unmatched_exp = _match_ingredients(extracted, expected)
        assert len(matched) == 1
        assert len(unmatched_ext) == 1
        assert len(unmatched_exp) == 1

    def test_empty_extracted(self):
        matched, unmatched_ext, unmatched_exp = _match_ingredients([], [{"name": "flour"}])
        assert len(matched) == 0
        assert len(unmatched_exp) == 1

    def test_fuzzy_match(self):
        extracted = [{"name": "all purpose flour"}]
        expected = [{"name": "all-purpose flour"}]
        matched, _, _ = _match_ingredients(extracted, expected)
        assert len(matched) == 1


# ---------------------------------------------------------------------------
# Scoring dimensions
# ---------------------------------------------------------------------------


class TestIngredientsPrecision:
    def test_perfect(self):
        ext = [{"name": "flour"}, {"name": "sugar"}]
        exp = [{"name": "flour"}, {"name": "sugar"}]
        assert _score_ingredients_precision(ext, exp) == 1.0

    def test_extra_extracted(self):
        ext = [{"name": "flour"}, {"name": "sugar"}, {"name": "salt"}]
        exp = [{"name": "flour"}, {"name": "sugar"}]
        assert _score_ingredients_precision(ext, exp) == pytest.approx(2 / 3)

    def test_empty(self):
        assert _score_ingredients_precision([], []) == 1.0
        assert _score_ingredients_precision([], [{"name": "flour"}]) == 0.0


class TestIngredientsRecall:
    def test_perfect(self):
        ext = [{"name": "flour"}, {"name": "sugar"}]
        exp = [{"name": "flour"}, {"name": "sugar"}]
        assert _score_ingredients_recall(ext, exp) == 1.0

    def test_missing(self):
        ext = [{"name": "flour"}]
        exp = [{"name": "flour"}, {"name": "sugar"}]
        assert _score_ingredients_recall(ext, exp) == 0.5

    def test_empty_expected(self):
        assert _score_ingredients_recall([{"name": "flour"}], []) == 1.0


class TestAmountsAccuracy:
    def test_perfect(self):
        ext = [{"name": "flour", "quantity": 2, "unit": "cups"}]
        exp = [{"name": "flour", "quantity": 2, "unit": "cups"}]
        assert _score_amounts_accuracy(ext, exp) == 1.0

    def test_unit_normalization(self):
        ext = [{"name": "flour", "quantity": 2, "unit": "cup"}]
        exp = [{"name": "flour", "quantity": 2, "unit": "cups"}]
        assert _score_amounts_accuracy(ext, exp) == 1.0

    def test_wrong_quantity(self):
        ext = [{"name": "flour", "quantity": 3, "unit": "cups"}]
        exp = [{"name": "flour", "quantity": 2, "unit": "cups"}]
        assert _score_amounts_accuracy(ext, exp) == 0.0

    def test_no_match(self):
        assert _score_amounts_accuracy([], []) == 0.0


class TestStepsCompleteness:
    def test_matching_instructions(self):
        extracted = {"instructions": "Preheat oven to 350. Mix flour and sugar. Bake for 30 minutes."}
        expected = {"instructions": "Preheat oven to 350. Mix flour and sugar. Bake for 30 minutes."}
        assert _score_steps_completeness(extracted, expected) == 1.0

    def test_partial_instructions(self):
        extracted = {"instructions": "Preheat oven to 350. Mix flour and sugar."}
        expected = {"instructions": "Preheat oven to 350. Mix flour and sugar. Bake for 30 minutes."}
        score = _score_steps_completeness(extracted, expected)
        assert 0.0 < score < 1.0

    def test_empty_expected(self):
        assert _score_steps_completeness({"instructions": "Do something."}, {}) == 1.0

    def test_empty_extracted(self):
        assert _score_steps_completeness({}, {"instructions": "Preheat oven to 350. Mix flour and sugar."}) == 0.0


class TestMetadataAccuracy:
    def test_all_correct(self):
        extracted = {
            "name": "Chocolate Cake",
            "prep_time_minutes": 15,
            "cook_time_minutes": 30,
            "servings": 8,
        }
        expected = {
            "name": "Chocolate Cake",
            "prep_time_minutes": 15,
            "cook_time_minutes": 30,
            "servings": 8,
        }
        assert _score_metadata_accuracy(extracted, expected) == 1.0

    def test_time_tolerance(self):
        extracted = {"prep_time_minutes": 17}
        expected = {"prep_time_minutes": 15}
        assert _score_metadata_accuracy(extracted, expected) == 1.0

    def test_wrong_servings(self):
        extracted = {"servings": 12}
        expected = {"servings": 4}
        assert _score_metadata_accuracy(extracted, expected) == 0.0

    def test_fuzzy_title(self):
        extracted = {"name": "chocolate cake"}
        expected = {"name": "Chocolate Cake"}
        assert _score_metadata_accuracy(extracted, expected) == 1.0


# ---------------------------------------------------------------------------
# Full score_extraction
# ---------------------------------------------------------------------------


class TestScoreExtraction:
    def test_perfect_score(self):
        recipe = {
            "name": "Test Recipe",
            "prep_time_minutes": 10,
            "cook_time_minutes": 20,
            "servings": 4,
            "ingredients": [
                {"name": "flour", "quantity": 2, "unit": "cups"},
                {"name": "sugar", "quantity": 1, "unit": "cup"},
            ],
            "instructions": "Mix flour and sugar together. Bake at 350 for 20 minutes.",
        }
        scores = score_extraction(recipe, recipe)
        assert scores["ingredients_precision"] == 1.0
        assert scores["ingredients_recall"] == 1.0
        assert scores["amounts_accuracy"] == 1.0
        assert scores["metadata_accuracy"] == 1.0
        assert scores["overall_f1"] > 0.9

    def test_all_keys_present(self):
        extracted = {"name": "X", "ingredients": [], "instructions": ""}
        expected = {"name": "Y", "ingredients": [], "instructions": ""}
        scores = score_extraction(extracted, expected)
        expected_keys = {
            "ingredients_precision",
            "ingredients_recall",
            "amounts_accuracy",
            "steps_completeness",
            "metadata_accuracy",
            "overall_f1",
        }
        assert expected_keys == set(scores.keys())

    def test_empty_extraction(self):
        scores = score_extraction({}, {"name": "Cake", "ingredients": [{"name": "flour"}]})
        assert scores["ingredients_recall"] == 0.0
        assert scores["overall_f1"] < 0.5
