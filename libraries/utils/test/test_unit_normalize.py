"""Unit tests for normalize_unit_display + log_unit_alias_miss."""

from __future__ import annotations

from typing import Any

import pytest

from utils.services.units import normalize as normalize_mod
from utils.services.units.normalize import (
    is_cache_initialized,
    normalize_unit_display,
    reload_unit_alias_cache,
    reset_unit_alias_cache_for_tests,
)


class _FakeSession:
    """Minimal stand-in for SQLAlchemy `Session.execute(...).scalars().all()`.

    The normalizer only ever calls `session.execute(select(Unit.name))`
    and `session.execute(select(UnitAlias.alias, UnitAlias.canonical_unit))`.
    """

    def __init__(self, canonical: list[str], aliases: list[tuple[str, str]]):
        self._canonical = canonical
        self._aliases = aliases
        self._calls: list[Any] = []

    def execute(self, stmt):  # noqa: ANN001
        self._calls.append(stmt)
        # The normalizer always issues two queries on a cache-load:
        #   1) select(Unit.name)                          → 1 column
        #   2) select(UnitAlias.alias, UnitAlias.canonical_unit) → 2 columns
        # Read the column count off the rendered statement to route.
        descriptions = stmt.column_descriptions
        if len(descriptions) == 1:
            return _ScalarsResult(self._canonical)
        return _RowsResult(self._aliases)


class _ScalarsResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return list(self._items)


class _RowsResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return [tuple(item) for item in self._items]


@pytest.fixture
def seeded_session():
    """Build a session pre-loaded with a small canonical/alias set."""
    return _FakeSession(
        canonical=["tbsp", "tsp", "cup", "g", "kg", "fl oz"],
        aliases=[
            ("tablespoon", "tbsp"),
            ("teaspoon", "tsp"),
            ("grams", "g"),
            ("kilogram", "kg"),
            ("fluid ounce", "fl oz"),
        ],
    )


@pytest.fixture(autouse=True)
def _clear_cache():
    """Each test starts with a fresh cache so lookups are deterministic."""
    reset_unit_alias_cache_for_tests()
    yield
    reset_unit_alias_cache_for_tests()


@pytest.fixture
def captured_misses(monkeypatch):
    """Replace `log_unit_alias_miss` with a spy."""
    misses: list[tuple[str, dict | None]] = []

    def _spy(raw, context=None):
        misses.append((raw, context))

    monkeypatch.setattr(normalize_mod, "log_unit_alias_miss", _spy)
    return misses


# ---------------------------------------------------------------------------
# Happy path: alias hits
# ---------------------------------------------------------------------------


def test_alias_hit_coerces_full_word_to_canonical(seeded_session, captured_misses):
    out = normalize_unit_display("tablespoon", seeded_session)
    assert out == "tbsp"
    assert captured_misses == []


def test_already_canonical_input_returns_as_is(seeded_session, captured_misses):
    out = normalize_unit_display("tbsp", seeded_session)
    assert out == "tbsp"
    assert captured_misses == []


def test_punctuation_and_case_stripped_before_lookup(seeded_session, captured_misses):
    """`Tbsp.` should fold to `tbsp` (punctuation + case)."""
    out = normalize_unit_display("Tbsp.", seeded_session)
    assert out == "tbsp"
    assert captured_misses == []


def test_canonical_with_space_preserved(seeded_session, captured_misses):
    out = normalize_unit_display("Fluid Ounce", seeded_session)
    assert out == "fl oz"
    assert captured_misses == []


# ---------------------------------------------------------------------------
# Misses: log + return normalized form
# ---------------------------------------------------------------------------


def test_unrecognized_unit_logs_miss_and_returns_normalized(
    seeded_session, captured_misses
):
    out = normalize_unit_display("weirdunit", seeded_session)
    # The miss returns the normalized input so callers persist a stable
    # token; raw is preserved in the audit row for grep-ability.
    assert out == "weirdunit"
    assert captured_misses == [("weirdunit", None)]


def test_miss_passes_context_to_logger(seeded_session, captured_misses):
    out = normalize_unit_display(
        "blortmeasure", seeded_session, context={"path": "extract_recipe_task"}
    )
    assert out == "blortmeasure"
    assert captured_misses == [
        ("blortmeasure", {"path": "extract_recipe_task"})
    ]


# ---------------------------------------------------------------------------
# None / empty paths
# ---------------------------------------------------------------------------


def test_none_input_returns_none(seeded_session, captured_misses):
    out = normalize_unit_display(None, seeded_session)
    assert out is None
    assert captured_misses == []


def test_empty_string_returns_unchanged(seeded_session, captured_misses):
    out = normalize_unit_display("", seeded_session)
    assert out == ""
    assert captured_misses == []


def test_whitespace_only_returns_unchanged(seeded_session, captured_misses):
    out = normalize_unit_display("   ", seeded_session)
    assert out == "   "
    assert captured_misses == []


# ---------------------------------------------------------------------------
# Cache lifecycle
# ---------------------------------------------------------------------------


def test_lazy_init_loads_cache_on_first_call(seeded_session, captured_misses):
    assert is_cache_initialized() is False
    normalize_unit_display("tablespoon", seeded_session)
    assert is_cache_initialized() is True


def test_explicit_reload_replaces_alias_map(seeded_session, captured_misses):
    """Reloading with a new alias swaps the resolved value."""
    reload_unit_alias_cache(seeded_session)
    assert normalize_unit_display("tablespoon", seeded_session) == "tbsp"

    bigger = _FakeSession(
        canonical=["tbsp", "tsp", "cup", "g"],
        aliases=[
            ("tablespoon", "tbsp"),
            ("largespoon", "tbsp"),  # newly added alias
        ],
    )
    reload_unit_alias_cache(bigger)
    assert normalize_unit_display("largespoon", bigger) == "tbsp"
