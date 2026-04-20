"""Unit tests for ``inference_guardrails.apply_guardrails``.

efi-1 — exercises per-field clamp / truncate / validate logic with a
spy-patched ``log_inferred_field_clamp`` so tests run without a
database. The ``ExtractedRecipe`` dataclass doesn't yet have an
``inferred_fields`` field (efi-2 adds it); the guardrails module
accesses the attribute via getattr/setattr so the test suite can stamp
the value on via ``setattr`` and round-trip through the helper.
"""

from __future__ import annotations

import pytest

from utils.services.recipe_extractors import inference_guardrails as gr_mod
from utils.services.recipe_extractors.base import (
    ExtractedIngredient,
    ExtractedRecipe,
)
from utils.services.recipe_extractors.inference_guardrails import apply_guardrails


@pytest.fixture
def captured_clamps(monkeypatch):
    """Replace ``log_inferred_field_clamp`` with a spy that records calls."""
    calls: list[dict] = []

    def _spy(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(gr_mod, "log_inferred_field_clamp", _spy)
    return calls


def _make_recipe(**overrides) -> ExtractedRecipe:
    base = {
        "name": "Test Recipe",
        "ingredients": [ExtractedIngredient(text="flour", quantity=1.0)],
        "instructions": "Mix and bake.",
    }
    base.update(overrides)
    recipe = ExtractedRecipe(**base)
    return recipe


# ---------------------------------------------------------------------------
# Empty / no-op cases
# ---------------------------------------------------------------------------


def test_no_inferred_fields_is_no_op(captured_clamps):
    recipe = _make_recipe()
    setattr(recipe, "inferred_fields", [])
    result = apply_guardrails(recipe, import_item_id=None)
    assert result is recipe
    assert getattr(recipe, "inferred_fields") == []
    assert captured_clamps == []


def test_missing_inferred_fields_attr_is_no_op(captured_clamps):
    # Defensive: ExtractedRecipe pre-efi-2 doesn't have the attr at all.
    recipe = _make_recipe()
    # Intentionally do NOT setattr — getattr default should kick in.
    result = apply_guardrails(recipe, import_item_id=None)
    assert result is recipe
    assert captured_clamps == []


def test_all_in_range_fields_pass_through_unchanged(captured_clamps):
    recipe = _make_recipe(
        prep_time_minutes=15,
        cook_time_minutes=30,
        servings=4,
        description="A tasty dish.",
        cuisine="Italian",
        category="Main",
        primary_vibe="comfort",
    )
    initial_inferred = [
        "prep_time_minutes",
        "cook_time_minutes",
        "servings",
        "description",
        "cuisine",
        "category",
        "primary_vibe",
    ]
    setattr(recipe, "inferred_fields", list(initial_inferred))
    apply_guardrails(recipe, import_item_id=None)
    assert recipe.prep_time_minutes == 15
    assert recipe.cook_time_minutes == 30
    assert recipe.servings == 4
    assert recipe.description == "A tasty dish."
    assert recipe.cuisine == "Italian"
    assert recipe.category == "Main"
    assert recipe.primary_vibe == "comfort"
    assert captured_clamps == []
    # Ordering preservation — the inferred_fields list must come out in
    # the same order it went in.
    assert getattr(recipe, "inferred_fields") == initial_inferred


# ---------------------------------------------------------------------------
# Numeric clamps (cook / prep / total / servings)
# ---------------------------------------------------------------------------


def test_cook_time_above_range_clamps_to_720(captured_clamps):
    recipe = _make_recipe(cook_time_minutes=1000)
    setattr(recipe, "inferred_fields", ["cook_time_minutes"])
    apply_guardrails(recipe, import_item_id="550e8400-e29b-41d4-a716-446655440000")
    assert recipe.cook_time_minutes == 720
    assert len(captured_clamps) == 1
    call = captured_clamps[0]
    assert call["field"] == "cook_time_minutes"
    assert call["raw"] == 1000
    assert call["clamped_or_dropped"] == 720
    assert call["reason"] == "out_of_range"


def test_cook_time_below_range_clamps_to_1(captured_clamps):
    recipe = _make_recipe(cook_time_minutes=0)
    setattr(recipe, "inferred_fields", ["cook_time_minutes"])
    apply_guardrails(recipe, import_item_id=None)
    assert recipe.cook_time_minutes == 1
    assert len(captured_clamps) == 1
    assert captured_clamps[0]["raw"] == 0
    assert captured_clamps[0]["clamped_or_dropped"] == 1


def test_prep_time_clamps_to_240(captured_clamps):
    recipe = _make_recipe(prep_time_minutes=500)
    setattr(recipe, "inferred_fields", ["prep_time_minutes"])
    apply_guardrails(recipe, import_item_id=None)
    assert recipe.prep_time_minutes == 240
    assert captured_clamps[0]["clamped_or_dropped"] == 240


def test_total_time_clamps_to_960(captured_clamps):
    recipe = _make_recipe(total_time_minutes=1_500)
    setattr(recipe, "inferred_fields", ["total_time_minutes"])
    apply_guardrails(recipe, import_item_id=None)
    assert recipe.total_time_minutes == 960
    assert captured_clamps[0]["clamped_or_dropped"] == 960


def test_bool_on_numeric_field_logged_as_invalid_type(captured_clamps):
    # bool is a subclass of int — a stray True/False shouldn't silently
    # become 1/0. Surface it as a type violation in the audit row so
    # the correction-log dashboard can distinguish type-errors from
    # range-errors.
    recipe = _make_recipe()
    setattr(recipe, "cook_time_minutes", True)
    setattr(recipe, "inferred_fields", ["cook_time_minutes"])
    apply_guardrails(recipe, import_item_id=None)
    assert recipe.cook_time_minutes is None
    assert captured_clamps[0]["field"] == "cook_time_minutes"
    assert captured_clamps[0]["reason"] == "invalid_type"


def test_servings_clamps_to_24(captured_clamps):
    recipe = _make_recipe(servings=100)
    setattr(recipe, "inferred_fields", ["servings"])
    apply_guardrails(recipe, import_item_id=None)
    assert recipe.servings == 24
    assert captured_clamps[0]["clamped_or_dropped"] == 24


# ---------------------------------------------------------------------------
# String truncation (description / cuisine / category)
# ---------------------------------------------------------------------------


def test_description_truncates_to_240_with_word_boundary(captured_clamps):
    long = (
        "This is a thoroughly long description that keeps describing "
        "the recipe in expansive detail — " + "word " * 200
    )
    recipe = _make_recipe(description=long)
    setattr(recipe, "inferred_fields", ["description"])
    apply_guardrails(recipe, import_item_id=None)
    assert recipe.description is not None
    assert len(recipe.description) <= 240
    # Word-boundary truncation means the tail should not end in a
    # mid-word cut.
    assert not recipe.description.endswith(" ")
    assert len(captured_clamps) == 1
    assert captured_clamps[0]["field"] == "description"
    assert captured_clamps[0]["reason"] == "too_long"


def test_description_no_space_falls_back_to_hard_truncate(captured_clamps):
    # Pathological case: a 500-char single-word "description" forces the
    # truncator to hard-cut at 240 (can't back up to a boundary without
    # discarding everything).
    recipe = _make_recipe(description="A" * 500)
    setattr(recipe, "inferred_fields", ["description"])
    apply_guardrails(recipe, import_item_id=None)
    assert recipe.description is not None
    assert len(recipe.description) == 240
    assert captured_clamps[0]["reason"] == "too_long"


def test_description_short_enough_no_truncation(captured_clamps):
    recipe = _make_recipe(description="Short description.")
    setattr(recipe, "inferred_fields", ["description"])
    apply_guardrails(recipe, import_item_id=None)
    assert recipe.description == "Short description."
    assert captured_clamps == []


def test_cuisine_truncates_to_40(captured_clamps):
    long_cuisine = "A" * 100
    recipe = _make_recipe(cuisine=long_cuisine)
    setattr(recipe, "inferred_fields", ["cuisine"])
    apply_guardrails(recipe, import_item_id=None)
    assert recipe.cuisine is not None
    assert len(recipe.cuisine) == 40
    assert captured_clamps[0]["field"] == "cuisine"


def test_category_truncates_to_40(captured_clamps):
    recipe = _make_recipe(category="B" * 100)
    setattr(recipe, "inferred_fields", ["category"])
    apply_guardrails(recipe, import_item_id=None)
    assert recipe.category is not None
    assert len(recipe.category) == 40
    assert captured_clamps[0]["field"] == "category"


# ---------------------------------------------------------------------------
# Vibe validation / drop behaviour
# ---------------------------------------------------------------------------


def test_invalid_primary_vibe_drops_and_removes_from_inferred(captured_clamps):
    recipe = _make_recipe(primary_vibe="bogus")
    setattr(recipe, "inferred_fields", ["primary_vibe"])
    apply_guardrails(recipe, import_item_id=None)
    assert recipe.primary_vibe is None
    assert getattr(recipe, "inferred_fields") == []
    assert len(captured_clamps) == 1
    assert captured_clamps[0]["field"] == "primary_vibe"
    assert captured_clamps[0]["reason"] == "invalid_vibe"
    assert captured_clamps[0]["clamped_or_dropped"] is None


def test_valid_vibe_is_kept_no_log(captured_clamps):
    recipe = _make_recipe(primary_vibe="comfort", secondary_vibe="hearty")
    setattr(recipe, "inferred_fields", ["primary_vibe", "secondary_vibe"])
    apply_guardrails(recipe, import_item_id=None)
    assert recipe.primary_vibe == "comfort"
    assert recipe.secondary_vibe == "hearty"
    assert set(getattr(recipe, "inferred_fields")) == {
        "primary_vibe",
        "secondary_vibe",
    }
    assert captured_clamps == []


def test_invalid_secondary_vibe_drops_primary_stays(captured_clamps):
    recipe = _make_recipe(primary_vibe="comfort", secondary_vibe="made_up")
    setattr(recipe, "inferred_fields", ["primary_vibe", "secondary_vibe"])
    apply_guardrails(recipe, import_item_id=None)
    assert recipe.primary_vibe == "comfort"
    assert recipe.secondary_vibe is None
    assert getattr(recipe, "inferred_fields") == ["primary_vibe"]
    assert len(captured_clamps) == 1
    assert captured_clamps[0]["field"] == "secondary_vibe"


# ---------------------------------------------------------------------------
# Combined + allow-list filter
# ---------------------------------------------------------------------------


def test_non_allow_listed_field_is_silently_dropped_from_inferred(
    captured_clamps,
):
    recipe = _make_recipe()
    setattr(recipe, "inferred_fields", ["cook_time_minutes", "name", "servings"])
    recipe.cook_time_minutes = 10
    recipe.servings = 4
    apply_guardrails(recipe, import_item_id=None)
    # `name` is filtered out silently — not an allowed inferable field.
    assert getattr(recipe, "inferred_fields") == [
        "cook_time_minutes",
        "servings",
    ]
    # Defense-in-depth filter is silent, no clamp logged for `name`.
    assert captured_clamps == []


def test_multiple_clamps_write_multiple_audit_rows(captured_clamps):
    recipe = _make_recipe(cook_time_minutes=9999, servings=99, primary_vibe="nope")
    setattr(
        recipe,
        "inferred_fields",
        ["cook_time_minutes", "servings", "primary_vibe"],
    )
    apply_guardrails(recipe, import_item_id=None)
    assert recipe.cook_time_minutes == 720
    assert recipe.servings == 24
    assert recipe.primary_vibe is None
    assert getattr(recipe, "inferred_fields") == [
        "cook_time_minutes",
        "servings",
    ]
    assert len(captured_clamps) == 3
    fields_logged = {c["field"] for c in captured_clamps}
    assert fields_logged == {"cook_time_minutes", "servings", "primary_vibe"}


def test_returns_same_recipe_object(captured_clamps):
    recipe = _make_recipe()
    setattr(recipe, "inferred_fields", [])
    result = apply_guardrails(recipe, import_item_id=None)
    assert result is recipe


def test_import_item_id_propagates_to_log_call(captured_clamps):
    recipe = _make_recipe(cook_time_minutes=5000)
    setattr(recipe, "inferred_fields", ["cook_time_minutes"])
    item_id = "550e8400-e29b-41d4-a716-446655440000"
    apply_guardrails(recipe, import_item_id=item_id)
    assert captured_clamps[0]["import_item_id"] == item_id
