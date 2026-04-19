"""Unit tests for `aggregate_meal_ingredients`.

The normalization layer is tested separately in test_unit_normalize.py —
here we stub `normalize_unit_display` to isolate the dedupe/sum logic.
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
    """Case-fold + trim as a stand-in for the real normalizer.

    The real normalize path is exercised in test_unit_normalize.py. Here
    we only care that `aggregate_meal_ingredients` uses whatever key the
    normalizer returns, so a deterministic lowercase/trim is enough.
    """

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
    category="produce",
):
    return SimpleNamespace(
        id=ingredient_id or uuid.uuid4(),
        canonical_name=canonical_name,
        category=category,
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
# Happy path: same-unit merge
# ---------------------------------------------------------------------------


def test_same_unit_merges_quantities(session):
    olive = _make_ingredient(canonical_name="olive oil", category="oils")
    r1 = _make_recipe(
        ingredients=[_make_recipe_ingredient(ingredient=olive, quantity=Decimal("1"), unit="tbsp")]
    )
    r2 = _make_recipe(
        ingredients=[_make_recipe_ingredient(ingredient=olive, quantity=Decimal("1"), unit="Tbsp")]
    )

    out = aggregate_meal_ingredients(_make_meal([r1, r2]), session)

    assert len(out) == 1
    row = out[0]
    assert row.ingredient_id == olive.id
    assert row.ingredient_name == "olive oil"
    assert row.category == "oils"
    assert row.summed_quantity == Decimal("2")
    assert row.normalized_unit == "tbsp"
    assert row.contributing_recipe_ids == [r1.id, r2.id]


def test_summed_quantity_preserves_decimal_precision(session):
    salt = _make_ingredient(canonical_name="salt")
    r1 = _make_recipe(
        ingredients=[_make_recipe_ingredient(ingredient=salt, quantity=Decimal("0.25"), unit="tsp")]
    )
    r2 = _make_recipe(
        ingredients=[_make_recipe_ingredient(ingredient=salt, quantity=Decimal("0.5"), unit="tsp")]
    )
    r3 = _make_recipe(
        ingredients=[_make_recipe_ingredient(ingredient=salt, quantity=Decimal("0.125"), unit="tsp")]
    )

    out = aggregate_meal_ingredients(_make_meal([r1, r2, r3]), session)

    assert out[0].summed_quantity == Decimal("0.875")


# ---------------------------------------------------------------------------
# Cross-unit NOT merged
# ---------------------------------------------------------------------------


def test_cross_unit_keeps_separate_rows(session):
    olive = _make_ingredient(canonical_name="olive oil")
    r1 = _make_recipe(
        ingredients=[_make_recipe_ingredient(ingredient=olive, quantity=Decimal("1"), unit="tbsp")]
    )
    r2 = _make_recipe(
        ingredients=[_make_recipe_ingredient(ingredient=olive, quantity=Decimal("15"), unit="ml")]
    )

    out = aggregate_meal_ingredients(_make_meal([r1, r2]), session)

    assert len(out) == 2
    units = {row.normalized_unit for row in out}
    assert units == {"tbsp", "ml"}
    for row in out:
        assert row.summed_quantity == (Decimal("1") if row.normalized_unit == "tbsp" else Decimal("15"))


# ---------------------------------------------------------------------------
# Null / empty unit
# ---------------------------------------------------------------------------


def test_null_unit_dedupes_on_empty_key(session):
    eggs = _make_ingredient(canonical_name="eggs", category="dairy")
    r1 = _make_recipe(
        ingredients=[_make_recipe_ingredient(ingredient=eggs, quantity=Decimal("2"), unit="")]
    )
    r2 = _make_recipe(
        ingredients=[_make_recipe_ingredient(ingredient=eggs, quantity=Decimal("2"), unit="")]
    )

    out = aggregate_meal_ingredients(_make_meal([r1, r2]), session)

    assert len(out) == 1
    assert out[0].summed_quantity == Decimal("4")
    assert out[0].normalized_unit == ""


def test_null_unit_distinct_from_specified_unit(session):
    eggs = _make_ingredient(canonical_name="eggs")
    # Unit-specified eggs and unit-less eggs should NOT merge — different keys.
    r1 = _make_recipe(
        ingredients=[_make_recipe_ingredient(ingredient=eggs, quantity=Decimal("2"), unit="")]
    )
    r2 = _make_recipe(
        ingredients=[_make_recipe_ingredient(ingredient=eggs, quantity=Decimal("1"), unit="cup")]
    )

    out = aggregate_meal_ingredients(_make_meal([r1, r2]), session)

    assert len(out) == 2


# ---------------------------------------------------------------------------
# Zero-ingredient components
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
    # Not an error/warning — just a debug trace.
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


# ---------------------------------------------------------------------------
# Archived components (skip + warn)
# ---------------------------------------------------------------------------


def test_archived_component_skipped_with_warning(session, caplog):
    live_salt = _make_ingredient(canonical_name="salt")
    archived_salt = _make_ingredient(canonical_name="salt")  # different id so we can assert exclusion
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
    assert out[0].summed_quantity == Decimal("1")
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
    # Insert a component whose recipe relationship is unexpectedly null.
    meal.components.insert(0, SimpleNamespace(recipe=None, recipe_id=uuid.uuid4()))

    with caplog.at_level(logging.DEBUG, logger="utils.services.meal_service"):
        out = aggregate_meal_ingredients(meal, session)

    assert len(out) == 1


# ---------------------------------------------------------------------------
# Contributing recipe ids ordering
# ---------------------------------------------------------------------------


def test_contributing_recipe_ids_preserve_insertion_order(session):
    olive = _make_ingredient(canonical_name="olive oil")
    r1 = _make_recipe(
        ingredients=[_make_recipe_ingredient(ingredient=olive, quantity=Decimal("1"), unit="tbsp")]
    )
    r2 = _make_recipe(
        ingredients=[_make_recipe_ingredient(ingredient=olive, quantity=Decimal("2"), unit="tbsp")]
    )
    r3 = _make_recipe(
        ingredients=[_make_recipe_ingredient(ingredient=olive, quantity=Decimal("3"), unit="tbsp")]
    )

    out = aggregate_meal_ingredients(_make_meal([r1, r2, r3]), session)

    assert out[0].contributing_recipe_ids == [r1.id, r2.id, r3.id]


def test_contributing_recipe_ids_deduped(session):
    """A single recipe with the same ingredient listed twice at the same
    unit still counts as one contributing recipe."""
    olive = _make_ingredient(canonical_name="olive oil")
    r = _make_recipe(
        ingredients=[
            _make_recipe_ingredient(ingredient=olive, quantity=Decimal("1"), unit="tbsp"),
            _make_recipe_ingredient(ingredient=olive, quantity=Decimal("2"), unit="tbsp"),
        ]
    )

    out = aggregate_meal_ingredients(_make_meal([r]), session)

    assert len(out) == 1
    assert out[0].contributing_recipe_ids == [r.id]
    assert out[0].summed_quantity == Decimal("3")


# ---------------------------------------------------------------------------
# Null ingredient relationship
# ---------------------------------------------------------------------------


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
# None quantity tolerated (defensive)
# ---------------------------------------------------------------------------


def test_none_quantity_treated_as_zero(session):
    olive = _make_ingredient(canonical_name="olive oil")
    r1 = _make_recipe(
        ingredients=[_make_recipe_ingredient(ingredient=olive, quantity=None, unit="tbsp")]
    )
    r2 = _make_recipe(
        ingredients=[_make_recipe_ingredient(ingredient=olive, quantity=Decimal("2"), unit="tbsp")]
    )

    out = aggregate_meal_ingredients(_make_meal([r1, r2]), session)

    assert out[0].summed_quantity == Decimal("2")


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
