"""Unit tests for ``inference_prompt`` — flag, rule, allow-list.

efi-1 — no network I/O; pure module-level tests with monkeypatched env.
"""

from __future__ import annotations

import pytest

from utils.services.recipe_extractors.inference_prompt import (
    INFERABLE_FIELDS,
    infer_missing_fields,
    inference_rule,
)


@pytest.fixture
def flag_off(monkeypatch):
    monkeypatch.setenv("EXTRACTOR_INFER_MISSING_FIELDS", "false")


@pytest.fixture
def flag_on(monkeypatch):
    monkeypatch.setenv("EXTRACTOR_INFER_MISSING_FIELDS", "true")


@pytest.fixture
def flag_unset(monkeypatch):
    monkeypatch.delenv("EXTRACTOR_INFER_MISSING_FIELDS", raising=False)


# ---------------------------------------------------------------------------
# Flag parsing (AC1)
# ---------------------------------------------------------------------------


def test_infer_missing_fields_default_on(flag_unset):
    assert infer_missing_fields() is True


def test_infer_missing_fields_explicit_on(flag_on):
    assert infer_missing_fields() is True


@pytest.mark.parametrize("value", ["false", "FALSE", "0", "no", "off", "No", "Off"])
def test_infer_missing_fields_off_values(monkeypatch, value):
    monkeypatch.setenv("EXTRACTOR_INFER_MISSING_FIELDS", value)
    assert infer_missing_fields() is False


@pytest.mark.parametrize("value", ["true", "1", "yes", "on", "anything_else"])
def test_infer_missing_fields_truthy_values(monkeypatch, value):
    monkeypatch.setenv("EXTRACTOR_INFER_MISSING_FIELDS", value)
    assert infer_missing_fields() is True


# ---------------------------------------------------------------------------
# Allow-list (AC1 — exactly 9 schema-valid field names)
# ---------------------------------------------------------------------------


def test_inferable_fields_has_exactly_nine_entries():
    assert len(INFERABLE_FIELDS) == 9


def test_inferable_fields_contents():
    expected = {
        "prep_time_minutes",
        "cook_time_minutes",
        "total_time_minutes",
        "servings",
        "description",
        "cuisine",
        "category",
        "primary_vibe",
        "secondary_vibe",
    }
    assert set(INFERABLE_FIELDS) == expected


def test_inferable_fields_is_tuple_and_immutable():
    assert isinstance(INFERABLE_FIELDS, tuple)


def test_inferable_fields_no_forbidden_names():
    # Names, ingredients, and steps must NEVER be inferable. Sanity
    # guard against accidental expansion.
    forbidden = {"name", "ingredients", "steps", "instructions", "source_url"}
    assert not forbidden & set(INFERABLE_FIELDS)


# ---------------------------------------------------------------------------
# Prompt fragment (AC2)
# ---------------------------------------------------------------------------


def test_inference_rule_empty_when_flag_off(flag_off):
    assert inference_rule() == ""


def test_inference_rule_nonempty_when_flag_on(flag_on):
    rule = inference_rule()
    assert rule
    assert len(rule) > 100


def test_inference_rule_mentions_inferred_fields_array(flag_on):
    rule = inference_rule()
    assert "inferred_fields" in rule


def test_inference_rule_lists_all_nine_field_names(flag_on):
    rule = inference_rule()
    for field in INFERABLE_FIELDS:
        assert field in rule, f"inference rule must name `{field}`"


def test_inference_rule_forbids_inferring_name_ingredients_steps(flag_on):
    rule = inference_rule()
    # Check the literal NEVER clause by substring — a loose "name in
    # rule" assertion would pass even if the ban was removed (the word
    # "name" appears elsewhere in normal prose like "schema name").
    assert "NEVER infer name" in rule
    assert "ingredients" in rule
    assert "steps" in rule


def test_inference_rule_has_worked_example(flag_on):
    rule = inference_rule()
    # Epic AC2(d) — "one worked example of an inferred cook_time_minutes".
    assert "Example" in rule or "example" in rule
    assert "cook_time_minutes" in rule


def test_inference_rule_requires_empty_array_when_nothing_inferred(flag_on):
    rule = inference_rule()
    # Mentions the empty-array requirement somehow.
    assert "[]" in rule or "empty" in rule.lower()
