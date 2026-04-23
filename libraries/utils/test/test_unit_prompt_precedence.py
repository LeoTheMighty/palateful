"""eri-1: flag precedence for the unit-rule prompt.

Precedence (documented in ``unit_prompt.py``):

    EXTRACTOR_SOFTEN_UNIT_RULE on    -> _SOFTENED_RULE
    EXTRACTOR_EMIT_CANONICAL_UNITS on -> _CANONICAL_RULE
    neither                          -> freeform_fallback

This module tests the 2x2 matrix + the default (both unset). The riip-3
baseline tests in ``test_extractor_unit_prompt.py`` keep passing under
the new default because SOFTEN is the new winner; those tests flip
``EXTRACTOR_EMIT_CANONICAL_UNITS`` which now only matters when SOFTEN is
explicitly off.
"""

from __future__ import annotations

import pytest

from utils.services.recipe_extractors.unit_prompt import (
    CANONICAL_UNIT_TOKENS,
    emit_canonical_units,
    soften_unit_rule,
    unit_rule,
)


_FREEFORM = "LEGACY-FREEFORM-FALLBACK"


def _set_flags(
    monkeypatch: pytest.MonkeyPatch,
    *,
    soften: str | None,
    canonical: str | None,
) -> None:
    for name, value in (
        ("EXTRACTOR_SOFTEN_UNIT_RULE", soften),
        ("EXTRACTOR_EMIT_CANONICAL_UNITS", canonical),
    ):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)


# ---------------------------------------------------------------------------
# Individual flag parsing
# ---------------------------------------------------------------------------


def test_soften_unit_rule_default_on(monkeypatch):
    monkeypatch.delenv("EXTRACTOR_SOFTEN_UNIT_RULE", raising=False)
    assert soften_unit_rule() is True


@pytest.mark.parametrize("value", ["false", "FALSE", "0", "no", "off"])
def test_soften_unit_rule_off_values(monkeypatch, value):
    monkeypatch.setenv("EXTRACTOR_SOFTEN_UNIT_RULE", value)
    assert soften_unit_rule() is False


@pytest.mark.parametrize("value", ["true", "1", "yes", "on", "anything"])
def test_soften_unit_rule_truthy_values(monkeypatch, value):
    monkeypatch.setenv("EXTRACTOR_SOFTEN_UNIT_RULE", value)
    assert soften_unit_rule() is True


# ---------------------------------------------------------------------------
# 2x2 matrix: SOFTEN x CANONICAL
# ---------------------------------------------------------------------------


def test_matrix_both_on_returns_softened(monkeypatch):
    _set_flags(monkeypatch, soften="true", canonical="true")
    out = unit_rule(freeform_fallback=_FREEFORM)
    assert _FREEFORM not in out
    # Softened rule signature
    assert "prefer one of these tokens" in out
    # Canonical rule signature should NOT appear
    assert "use EXACTLY one of these tokens" not in out


def test_matrix_soften_on_canonical_off_returns_softened(monkeypatch):
    _set_flags(monkeypatch, soften="true", canonical="false")
    out = unit_rule(freeform_fallback=_FREEFORM)
    assert _FREEFORM not in out
    assert "prefer one of these tokens" in out
    assert "use EXACTLY one of these tokens" not in out


def test_matrix_soften_off_canonical_on_returns_canonical(monkeypatch):
    _set_flags(monkeypatch, soften="false", canonical="true")
    out = unit_rule(freeform_fallback=_FREEFORM)
    assert _FREEFORM not in out
    assert "use EXACTLY one of these tokens" in out
    assert "prefer one of these tokens" not in out


def test_matrix_both_off_returns_freeform(monkeypatch):
    _set_flags(monkeypatch, soften="false", canonical="false")
    out = unit_rule(freeform_fallback=_FREEFORM)
    assert out == _FREEFORM


# ---------------------------------------------------------------------------
# Unset default: both unset -> SOFTEN wins (default-on)
# ---------------------------------------------------------------------------


def test_both_unset_defaults_to_softened(monkeypatch):
    _set_flags(monkeypatch, soften=None, canonical=None)
    out = unit_rule(freeform_fallback=_FREEFORM)
    assert "prefer one of these tokens" in out
    assert _FREEFORM not in out


# ---------------------------------------------------------------------------
# Softened rule content
# ---------------------------------------------------------------------------


def test_softened_rule_lists_every_canonical_token(monkeypatch):
    _set_flags(monkeypatch, soften="true", canonical="false")
    out = unit_rule(freeform_fallback=_FREEFORM)
    for token in CANONICAL_UNIT_TOKENS:
        assert f"`{token}`" in out, f"missing `{token}` in softened rule"


def test_softened_rule_mentions_freeform_allowed_words(monkeypatch):
    _set_flags(monkeypatch, soften="true", canonical="false")
    out = unit_rule(freeform_fallback=_FREEFORM)
    # A few spot-checks from the freeform-allowed list.
    for word in ("stalk", "bunch", "sprig", "head", "can", "drop"):
        assert f"`{word}`" in out


def test_softened_rule_biases_toward_convertible_units(monkeypatch):
    _set_flags(monkeypatch, soften="true", canonical="false")
    out = unit_rule(freeform_fallback=_FREEFORM)
    assert "convertible" in out.lower()
    # Convertible list spot-check
    for unit in ("cup", "tbsp", "tsp", "ml", "l", "g", "kg", "oz", "lb", "fl oz"):
        assert f"`{unit}`" in out


def test_softened_rule_respects_count_null(monkeypatch):
    _set_flags(monkeypatch, soften="true", canonical="false")
    out = unit_rule(freeform_fallback=_FREEFORM)
    # "3 large eggs" -> unit: null is explicit in the rule
    assert "3 large eggs" in out
    assert "unit: null" in out


# ---------------------------------------------------------------------------
# Call-time read guard: flag flip between two calls takes effect instantly
# ---------------------------------------------------------------------------


def test_flag_is_read_at_call_time_not_module_load(monkeypatch):
    _set_flags(monkeypatch, soften="true", canonical="true")
    first = unit_rule(freeform_fallback=_FREEFORM)
    assert "prefer one of these tokens" in first

    _set_flags(monkeypatch, soften="false", canonical="true")
    second = unit_rule(freeform_fallback=_FREEFORM)
    assert "use EXACTLY one of these tokens" in second

    _set_flags(monkeypatch, soften="false", canonical="false")
    third = unit_rule(freeform_fallback=_FREEFORM)
    assert third == _FREEFORM


# ---------------------------------------------------------------------------
# Regression pin: emit_canonical_units() still reads its own env var
# ---------------------------------------------------------------------------


def test_emit_canonical_units_flag_still_independently_honored(monkeypatch):
    monkeypatch.setenv("EXTRACTOR_EMIT_CANONICAL_UNITS", "false")
    assert emit_canonical_units() is False
    monkeypatch.setenv("EXTRACTOR_EMIT_CANONICAL_UNITS", "true")
    assert emit_canonical_units() is True
