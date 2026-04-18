"""riip-3: extractor prompts emit canonical token list when flag is on.

Each extractor's prompt builder is tested directly. We don't call OpenAI
in the test — the assertion is that the prompt *string* contains the
canonical token list when EXTRACTOR_EMIT_CANONICAL_UNITS=true and the
legacy freeform instruction when false.
"""

from __future__ import annotations

import pytest

from utils.services.recipe_extractors import ai_extractor as ai_mod
from utils.services.recipe_extractors import text_extractor as text_mod
from utils.services.recipe_extractors import vision_extractor as vision_mod
from utils.services.recipe_extractors.unit_prompt import (
    CANONICAL_UNIT_TOKENS,
    emit_canonical_units,
    unit_rule,
)


@pytest.fixture
def flag_off(monkeypatch):
    monkeypatch.setenv("EXTRACTOR_EMIT_CANONICAL_UNITS", "false")


@pytest.fixture
def flag_on(monkeypatch):
    monkeypatch.setenv("EXTRACTOR_EMIT_CANONICAL_UNITS", "true")


@pytest.fixture
def flag_unset(monkeypatch):
    monkeypatch.delenv("EXTRACTOR_EMIT_CANONICAL_UNITS", raising=False)


# ---------------------------------------------------------------------------
# Flag parsing
# ---------------------------------------------------------------------------


def test_emit_canonical_units_default_on(flag_unset):
    assert emit_canonical_units() is True


@pytest.mark.parametrize("value", ["false", "FALSE", "False", "0", "no", "off"])
def test_emit_canonical_units_off_values(monkeypatch, value):
    monkeypatch.setenv("EXTRACTOR_EMIT_CANONICAL_UNITS", value)
    assert emit_canonical_units() is False


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "on", "anything-else"])
def test_emit_canonical_units_truthy_values(monkeypatch, value):
    monkeypatch.setenv("EXTRACTOR_EMIT_CANONICAL_UNITS", value)
    assert emit_canonical_units() is True


# ---------------------------------------------------------------------------
# unit_rule contents
# ---------------------------------------------------------------------------


def test_unit_rule_when_on_lists_every_canonical_token(flag_on):
    out = unit_rule(freeform_fallback="LEGACY")
    for token in CANONICAL_UNIT_TOKENS:
        assert f"`{token}`" in out
    assert "LEGACY" not in out
    # The rule explicitly forbids full words + punctuation.
    assert "Do not write out full words" in out
    assert "Do not add trailing punctuation" in out


def test_unit_rule_when_off_returns_freeform_fallback(flag_off):
    out = unit_rule(freeform_fallback="LEGACY-INSTRUCTION-HERE")
    assert out == "LEGACY-INSTRUCTION-HERE"


# ---------------------------------------------------------------------------
# Per-extractor prompt content (riip-3 AC8)
# ---------------------------------------------------------------------------


def _assert_prompt_has_canonical(prompt: str) -> None:
    for token in CANONICAL_UNIT_TOKENS:
        assert f"`{token}`" in prompt, f"missing `{token}` in prompt"


def test_ai_extractor_prompt_contains_canonical_tokens_when_on(flag_on):
    _assert_prompt_has_canonical(ai_mod._extraction_prompt())  # noqa: SLF001


def test_text_extractor_prompt_contains_canonical_tokens_when_on(flag_on):
    _assert_prompt_has_canonical(text_mod._text_extraction_prompt())  # noqa: SLF001


def test_vision_extractor_prompt_contains_canonical_tokens_when_on(flag_on):
    _assert_prompt_has_canonical(vision_mod._vision_system_prompt())  # noqa: SLF001


def test_ai_extractor_prompt_falls_back_to_freeform_when_off(flag_off):
    out = ai_mod._extraction_prompt()  # noqa: SLF001
    # Freeform mention of "tablespoon" is preserved.
    assert "tablespoon" in out
    # Canonical token-list bullet is NOT present.
    assert "use EXACTLY one of these tokens" not in out


def test_text_extractor_prompt_falls_back_to_freeform_when_off(flag_off):
    out = text_mod._text_extraction_prompt()  # noqa: SLF001
    assert "tablespoon" in out
    assert "use EXACTLY one of these tokens" not in out


def test_vision_extractor_prompt_falls_back_to_freeform_when_off(flag_off):
    out = vision_mod._vision_system_prompt()  # noqa: SLF001
    assert "tablespoon" in out
    assert "use EXACTLY one of these tokens" not in out


# ---------------------------------------------------------------------------
# Sanity: the canonical seed in the migration matches the prompt list
# ---------------------------------------------------------------------------


def test_canonical_token_list_matches_seed_migration():
    """The prompt's canonical token list must match what's seeded in
    `units` so a model that obeys the prompt produces a value the
    normalizer accepts as canonical (no audit miss)."""
    # Imported lazily — the migration file isn't on the regular import
    # path, but we read its source to extract the tuple.
    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[3]
        / "services/migrator/migrations/versions/"
        "20260418040000_create_unit_aliases.py"
    )
    text = migration.read_text()
    # Pull every `("name", ...)` tuple at the top of _CANONICAL_UNITS.
    import re

    block = text.split("_CANONICAL_UNITS")[1].split(")\n\n\n# alias")[0]
    seeded_names = set(re.findall(r'\("([^"]+)"\s*,', block))
    prompt_names = set(CANONICAL_UNIT_TOKENS)
    assert prompt_names == seeded_names, (
        "Prompt token list and migration seed are out of sync: "
        f"only-in-prompt={prompt_names - seeded_names}, "
        f"only-in-seed={seeded_names - prompt_names}"
    )
