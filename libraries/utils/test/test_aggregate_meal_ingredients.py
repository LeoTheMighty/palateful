"""Unit tests for `aggregate_meal_ingredients`.

Post-epic-ingredients-string-simplification: no dedup, one output row
per input `recipe_ingredients` row, preserving component × ingredient
order. The normalization layer is tested separately in
test_unit_normalize.py — here we stub `normalize_unit_display` to
isolate the flat-emission logic.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from utils.services import meal_service
from utils.services.meal_service import (
    AggregatedIngredient,
    aggregate_meal_ingredients,
)


class _FakeSession:
    """Stand-in; aggregate_meal_ingredients never touches the session
    directly — the only use is passing it through to normalize_unit_display
    which we stub below."""


@pytest.fixture
def session():
    return _FakeSession()


@pytest.fixture(autouse=True)
def stub_normalize(monkeypatch):
    """Case-fold + trim as a stand-in for the real normalizer."""

    def _fake(raw, session, **_kwargs):
        if raw is None:
            return None
        return raw.strip().lower()

    monkeypatch.setattr(meal_service, "normalize_unit_display", _fake)
    return _fake


def _make_ingredient(
    *,
    ingredient_id=None,
    canonical_name="ingredient",
):
    return SimpleNamespace(
        id=ingredient_id or uuid.uuid4(),
        canonical_name=canonical_name,
    )


def _make_recipe_ingredient(
    *,
    ingredient,
    quantity=Decimal("1"),
    unit="tbsp",
    archived=False,
):
    return SimpleNamespace(
        ingredient=ingredient,
        ingredient_id=ingredient.id,
        quantity_display=quantity,
        unit_display=unit,
        archived_at=None if not archived else "2026-01-01",
    )


def _make_recipe(
    *,
    recipe_id=None,
    ingredients=None,
    archived=False,
    book_archived=False,
):
    book = SimpleNamespace(
        id=uuid.uuid4(),
        archived_at=None if not book_archived else "2026-01-01",
    )
    return SimpleNamespace(
        id=recipe_id or uuid.uuid4(),
        archived_at=None if not archived else "2026-01-01",
        recipe_book=book,
        ingredients=ingredients or [],
    )


def _make_meal(components):
    meal_components = [
        SimpleNamespace(recipe=c, recipe_id=c.id if c is not None else None)
        for c in components
    ]
    return SimpleNamespace(id=uuid.uuid4(), components=meal_components)


# ---------------------------------------------------------------------------
# Positive: one row per recipe_ingredient, no dedup
# ---------------------------------------------------------------------------


def test_aggregate_emits_one_row_per_recipe_ingredient_even_on_overlap(session):
    """Two recipes each using olive oil → two rows, not one merged row."""
    olive_a = _make_ingredient(canonical_name="olive oil")
    olive_b = _make_ingredient(canonical_name="olive oil")
    r1 = _make_recipe(
        ingredients=[_make_recipe_ingredient(ingredient=olive_a, quantity=Decimal("1"), unit="tbsp")]
    )
    r2 = _make_recipe(
        ingredients=[_make_recipe_ingredient(ingredient=olive_b, quantity=Decimal("1"), unit="tbsp")]
    )

    out = aggregate_meal_ingredients(_make_meal([r1, r2]), session)

    assert len(out) == 2
    assert [row.ingredient_name for row in out] == ["olive oil", "olive oil"]
    assert [row.summed_quantity for row in out] == [Decimal("1"), Decimal("1")]
    # Each row's `category` is always None post-epic — the column is
    # being dropped and no handler reads it anymore.
    assert all(row.category is None for row in out)


def test_aggregate_preserves_component_then_ingredient_order(session):
    """Fixture with 3 components × 2 ingredients each; order matches concat."""
    c1_salt = _make_ingredient(canonical_name="salt")
    c1_pepper = _make_ingredient(canonical_name="pepper")
    c2_sugar = _make_ingredient(canonical_name="sugar")
    c2_flour = _make_ingredient(canonical_name="flour")
    c3_oil = _make_ingredient(canonical_name="olive oil")
    c3_garlic = _make_ingredient(canonical_name="garlic")

    r1 = _make_recipe(
        ingredients=[
            _make_recipe_ingredient(ingredient=c1_salt, unit="tsp"),
            _make_recipe_ingredient(ingredient=c1_pepper, unit="tsp"),
        ]
    )
    r2 = _make_recipe(
        ingredients=[
            _make_recipe_ingredient(ingredient=c2_sugar, unit="tbsp"),
            _make_recipe_ingredient(ingredient=c2_flour, unit="cup"),
        ]
    )
    r3 = _make_recipe(
        ingredients=[
            _make_recipe_ingredient(ingredient=c3_oil, unit="tbsp"),
            _make_recipe_ingredient(ingredient=c3_garlic, unit="clove"),
        ]
    )

    out = aggregate_meal_ingredients(_make_meal([r1, r2, r3]), session)

    assert [row.ingredient_name for row in out] == [
        "salt", "pepper", "sugar", "flour", "olive oil", "garlic",
    ]


def test_len_equals_sum_of_live_ingredients(session):
    """len(result) == sum(len(r.ingredients) for r in components)."""
    ingredient = _make_ingredient(canonical_name="thing")
    r1 = _make_recipe(
        ingredients=[_make_recipe_ingredient(ingredient=ingredient) for _ in range(3)]
    )
    r2 = _make_recipe(
        ingredients=[_make_recipe_ingredient(ingredient=ingredient) for _ in range(5)]
    )

    out = aggregate_meal_ingredients(_make_meal([r1, r2]), session)

    assert len(out) == 8


def test_contributing_recipe_ids_has_exactly_one_element_per_row(session):
    """Back-compat: downstream consumers still iterate contributing_recipe_ids."""
    olive = _make_ingredient(canonical_name="olive oil")
    r = _make_recipe(
        ingredients=[
            _make_recipe_ingredient(ingredient=olive, quantity=Decimal("1"), unit="tbsp"),
            _make_recipe_ingredient(ingredient=olive, quantity=Decimal("2"), unit="tbsp"),
        ]
    )

    out = aggregate_meal_ingredients(_make_meal([r]), session)

    assert len(out) == 2
    assert [row.contributing_recipe_ids for row in out] == [[r.id], [r.id]]


# ---------------------------------------------------------------------------
# Edge: empty / archived / missing recipes
# ---------------------------------------------------------------------------


def test_zero_ingredient_component_skipped_cleanly(session, caplog):
    olive = _make_ingredient(canonical_name="olive oil")
    empty_recipe = _make_recipe(ingredients=[])
    populated_recipe = _make_recipe(
        ingredients=[_make_recipe_ingredient(ingredient=olive, quantity=Decimal("1"), unit="tbsp")]
    )

    with caplog.at_level(logging.DEBUG, logger="utils.services.meal_service"):
        out = aggregate_meal_ingredients(
            _make_meal([empty_recipe, populated_recipe]), session
        )

    assert len(out) == 1
    assert out[0].ingredient_id == olive.id
    assert not any(record.levelno >= logging.WARNING for record in caplog.records)


def test_component_with_only_archived_ingredients_treated_as_empty(session):
    olive = _make_ingredient(canonical_name="olive oil")
    r = _make_recipe(
        ingredients=[
            _make_recipe_ingredient(
                ingredient=olive, quantity=Decimal("1"), unit="tbsp", archived=True
            )
        ]
    )

    out = aggregate_meal_ingredients(_make_meal([r]), session)

    assert out == []


def test_archived_component_skipped_with_warning(session, caplog):
    live_salt = _make_ingredient(canonical_name="salt")
    archived_salt = _make_ingredient(canonical_name="salt")
    archived_recipe = _make_recipe(
        archived=True,
        ingredients=[
            _make_recipe_ingredient(ingredient=archived_salt, quantity=Decimal("2"), unit="tsp")
        ],
    )
    live_recipe = _make_recipe(
        ingredients=[
            _make_recipe_ingredient(ingredient=live_salt, quantity=Decimal("1"), unit="tsp")
        ]
    )

    with caplog.at_level(logging.WARNING, logger="utils.services.meal_service"):
        out = aggregate_meal_ingredients(
            _make_meal([archived_recipe, live_recipe]), session
        )

    assert len(out) == 1
    assert out[0].ingredient_id == live_salt.id
    assert any(
        "archived" in record.getMessage().lower()
        and "skipping" in record.getMessage().lower()
        for record in caplog.records
    )


def test_archived_book_skipped_with_warning(session, caplog):
    live_salt = _make_ingredient(canonical_name="salt")
    archived_book_recipe = _make_recipe(
        book_archived=True,
        ingredients=[
            _make_recipe_ingredient(ingredient=live_salt, quantity=Decimal("1"), unit="tsp")
        ],
    )

    with caplog.at_level(logging.WARNING, logger="utils.services.meal_service"):
        out = aggregate_meal_ingredients(_make_meal([archived_book_recipe]), session)

    assert out == []
    assert any(
        "archived" in record.getMessage().lower() for record in caplog.records
    )


def test_null_recipe_relationship_skipped_silently(session, caplog):
    olive = _make_ingredient(canonical_name="olive oil")
    live_recipe = _make_recipe(
        ingredients=[
            _make_recipe_ingredient(ingredient=olive, quantity=Decimal("1"), unit="tbsp")
        ]
    )
    meal = _make_meal([live_recipe])
    meal.components.insert(0, SimpleNamespace(recipe=None, recipe_id=uuid.uuid4()))

    with caplog.at_level(logging.DEBUG, logger="utils.services.meal_service"):
        out = aggregate_meal_ingredients(meal, session)

    assert len(out) == 1


def test_null_ingredient_relationship_skipped(session):
    olive = _make_ingredient(canonical_name="olive oil")
    orphan_ri = SimpleNamespace(
        ingredient=None,
        ingredient_id=uuid.uuid4(),
        quantity_display=Decimal("1"),
        unit_display="tbsp",
        archived_at=None,
    )
    r = _make_recipe(
        ingredients=[
            orphan_ri,
            _make_recipe_ingredient(ingredient=olive, quantity=Decimal("1"), unit="tbsp"),
        ]
    )

    out = aggregate_meal_ingredients(_make_meal([r]), session)

    assert len(out) == 1
    assert out[0].ingredient_id == olive.id


# ---------------------------------------------------------------------------
# Null quantity tolerated (defensive)
# ---------------------------------------------------------------------------


def test_none_quantity_treated_as_zero(session):
    olive = _make_ingredient(canonical_name="olive oil")
    r = _make_recipe(
        ingredients=[_make_recipe_ingredient(ingredient=olive, quantity=None, unit="tbsp")]
    )

    out = aggregate_meal_ingredients(_make_meal([r]), session)

    assert out[0].summed_quantity == Decimal("0")


# ---------------------------------------------------------------------------
# Output type + shape
# ---------------------------------------------------------------------------


def test_output_is_list_of_aggregated_ingredient(session):
    olive = _make_ingredient(canonical_name="olive oil")
    r = _make_recipe(
        ingredients=[_make_recipe_ingredient(ingredient=olive, quantity=Decimal("1"), unit="tbsp")]
    )

    out = aggregate_meal_ingredients(_make_meal([r]), session)

    assert isinstance(out, list)
    assert all(isinstance(row, AggregatedIngredient) for row in out)


def test_empty_meal_returns_empty_list(session):
    out = aggregate_meal_ingredients(_make_meal([]), session)
    assert out == []
