"""Tests for the shelf-life estimator service."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from utils.services import shelf_life_service as sls


@pytest.fixture(autouse=True)
def _reset_cache():
    sls._reset_cache_for_tests()
    yield
    sls._reset_cache_for_tests()


def _ingredient(category=None):
    ing = MagicMock()
    ing.category = category
    return ing


def test_happy_path_fridge():
    added = datetime(2026, 4, 16, tzinfo=UTC)
    got = sls.estimate_expires_at(_ingredient("eggs"), "fridge", added_at=added)
    assert got is not None
    # eggs fridge_days is 35 in the seed
    assert got == added + timedelta(days=35)


def test_happy_path_pantry():
    added = datetime(2026, 4, 16, tzinfo=UTC)
    got = sls.estimate_expires_at(_ingredient("rice"), "pantry", added_at=added)
    assert got == added + timedelta(days=730)


def test_happy_path_freezer():
    added = datetime(2026, 4, 16, tzinfo=UTC)
    got = sls.estimate_expires_at(_ingredient("raw_chicken"), "freezer", added_at=added)
    assert got == added + timedelta(days=270)


def test_null_value_returns_none():
    """leafy_greens have null pantry_days — should return None."""
    got = sls.estimate_expires_at(_ingredient("leafy_greens"), "pantry")
    assert got is None


def test_none_storage_location_returns_none():
    got = sls.estimate_expires_at(_ingredient("eggs"), None)
    assert got is None


def test_unknown_storage_location_returns_none():
    got = sls.estimate_expires_at(_ingredient("eggs"), "garage")
    assert got is None


def test_unknown_category_falls_back_to_default():
    added = datetime(2026, 4, 16, tzinfo=UTC)
    got = sls.estimate_expires_at(_ingredient("unicorn_meat"), "fridge", added_at=added)
    # _default fridge_days is 5
    assert got == added + timedelta(days=5)


def test_none_category_falls_back_to_default():
    added = datetime(2026, 4, 16, tzinfo=UTC)
    got = sls.estimate_expires_at(_ingredient(None), "pantry", added_at=added)
    assert got == added + timedelta(days=14)  # _default pantry_days


def test_none_ingredient_falls_back_to_default():
    added = datetime(2026, 4, 16, tzinfo=UTC)
    got = sls.estimate_expires_at(None, "fridge", added_at=added)
    assert got == added + timedelta(days=5)  # _default fridge_days


def test_added_at_defaults_to_now(monkeypatch):
    # Two back-to-back calls without added_at should produce expires_at that
    # are monotonically non-decreasing (not exactly equal because now() ticks).
    a = sls.estimate_expires_at(_ingredient("eggs"), "fridge")
    b = sls.estimate_expires_at(_ingredient("eggs"), "fridge")
    assert a is not None and b is not None
    assert b >= a


def test_cache_is_populated_once():
    sls.load_shelf_life_data()
    assert sls._CACHE is not None
    first = sls._CACHE
    # A second load returns the same cached dict object.
    second = sls.load_shelf_life_data()
    assert second is first


def test_seed_file_parses_and_validates_shape():
    data = sls.load_shelf_life_data()
    # _default is present
    assert "_default" in data
    # Every entry has the three canonical keys
    for category, values in data.items():
        for key in ("fridge_days", "pantry_days", "freezer_days"):
            assert key in values, f"{category} missing {key}"
            assert values[key] is None or (
                isinstance(values[key], int) and values[key] > 0
            )


def test_seed_has_at_least_40_categories():
    data = sls.load_shelf_life_data()
    # _default doesn't count toward the 40-category requirement
    categories = [k for k in data if not k.startswith("_")]
    assert len(categories) >= 40, f"Only {len(categories)} categories seeded"


def test_eggs_fridge_days_in_sane_range():
    """Spot-check to catch obviously wrong edits to the seed."""
    data = sls.load_shelf_life_data()
    eggs = data["eggs"]
    assert 14 <= eggs["fridge_days"] <= 45


def test_raw_chicken_freezer_reasonable():
    data = sls.load_shelf_life_data()
    assert 60 <= data["raw_chicken"]["freezer_days"] <= 365
