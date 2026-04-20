"""Per-extractor prompt + parsing tests for efi-2.

Covers all three LLM extractors (ai, vision, text):
- Flag-on prompt contains the inference rule + all 9 field names + the
  ``inferred_fields`` array in the JSON skeleton.
- Flag-off prompt contains none of the above AND keeps the original
  "only include present fields" phrasing intact.
- ``_parse_*_response`` populates ``recipe.inferred_fields`` with the
  filtered + deduped allow-list, defaulting to ``[]`` for missing /
  null / malformed payloads.

No network I/O — extractor post-parse methods are called directly with
pre-baked mock payloads, so the tests run without an OpenAI client and
without any LLM spend.
"""

from __future__ import annotations

import pytest

from utils.services.recipe_extractors.ai_extractor import (
    AIExtractor,
    _extraction_prompt,
)
from utils.services.recipe_extractors.base import ExtractedRecipe
from utils.services.recipe_extractors.inference_prompt import (
    INFERABLE_FIELDS,
    parse_inferred_fields,
)
from utils.services.recipe_extractors.text_extractor import (
    _parse_response as _parse_text_response,
    _text_extraction_prompt,
)
from utils.services.recipe_extractors.vision_extractor import (
    _parse_response as _parse_vision_response,
    _vision_system_prompt,
)


@pytest.fixture
def flag_on(monkeypatch):
    monkeypatch.setenv("EXTRACTOR_INFER_MISSING_FIELDS", "true")


@pytest.fixture
def flag_off(monkeypatch):
    monkeypatch.setenv("EXTRACTOR_INFER_MISSING_FIELDS", "false")


# ---------------------------------------------------------------------------
# parse_inferred_fields helper (AC on parsing is consistent across extractors)
# ---------------------------------------------------------------------------


def test_parse_inferred_fields_none_returns_empty():
    assert parse_inferred_fields(None) == []


def test_parse_inferred_fields_non_list_returns_empty():
    assert parse_inferred_fields("cook_time_minutes") == []
    assert parse_inferred_fields({"cook_time_minutes": True}) == []
    assert parse_inferred_fields(42) == []


def test_parse_inferred_fields_filters_to_allow_list():
    raw = ["cook_time_minutes", "bogus_field", "servings", "name"]
    assert parse_inferred_fields(raw) == ["cook_time_minutes", "servings"]


def test_parse_inferred_fields_deduplicates_preserving_order():
    raw = ["cook_time_minutes", "servings", "cook_time_minutes"]
    assert parse_inferred_fields(raw) == ["cook_time_minutes", "servings"]


def test_parse_inferred_fields_trims_whitespace():
    raw = [" cook_time_minutes ", "servings"]
    assert parse_inferred_fields(raw) == ["cook_time_minutes", "servings"]


def test_parse_inferred_fields_ignores_non_strings():
    raw = ["cook_time_minutes", 42, None, {"servings": True}, "servings"]
    assert parse_inferred_fields(raw) == ["cook_time_minutes", "servings"]


def test_parse_inferred_fields_empty_list_returns_empty():
    assert parse_inferred_fields([]) == []


# ---------------------------------------------------------------------------
# AI extractor prompt + parsing
# ---------------------------------------------------------------------------


def test_ai_prompt_flag_on_contains_inferred_fields_and_all_nine_names(flag_on):
    prompt = _extraction_prompt()
    assert "inferred_fields" in prompt
    for field in INFERABLE_FIELDS:
        assert field in prompt, f"ai prompt must name `{field}`"


def test_ai_prompt_flag_off_omits_inference_language(flag_off):
    prompt = _extraction_prompt()
    # AC7: flag-off prompt must not mention `inferred_fields` AT ALL.
    # Otherwise the model is primed to emit the key even when we told
    # it not to.
    assert "inferred_fields" not in prompt
    assert "NEVER infer name" not in prompt
    assert "Field-level inference" not in prompt


def test_ai_prompt_flag_off_keeps_original_include_phrase(flag_off):
    prompt = _extraction_prompt()
    assert "Only include fields you can find in the content" in prompt


def test_ai_extractor_parses_inferred_fields():
    extractor = AIExtractor()
    data = {
        "name": "Test",
        "ingredients": [],
        "inferred_fields": ["cook_time_minutes", "servings"],
    }
    recipe = extractor._parse_ai_response(data)
    assert recipe.inferred_fields == ["cook_time_minutes", "servings"]


def test_ai_extractor_filters_bogus_inferred_fields():
    extractor = AIExtractor()
    data = {
        "name": "Test",
        "ingredients": [],
        "inferred_fields": ["cook_time_minutes", "bogus", "name"],
    }
    recipe = extractor._parse_ai_response(data)
    assert recipe.inferred_fields == ["cook_time_minutes"]


def test_ai_extractor_missing_inferred_fields_defaults_to_empty():
    extractor = AIExtractor()
    data = {"name": "Test", "ingredients": []}
    recipe = extractor._parse_ai_response(data)
    assert recipe.inferred_fields == []


def test_ai_extractor_null_inferred_fields_defaults_to_empty():
    extractor = AIExtractor()
    data = {"name": "Test", "ingredients": [], "inferred_fields": None}
    recipe = extractor._parse_ai_response(data)
    assert recipe.inferred_fields == []


def test_ai_extractor_deduplicates_inferred_fields():
    extractor = AIExtractor()
    data = {
        "name": "Test",
        "ingredients": [],
        "inferred_fields": ["servings", "servings", "servings"],
    }
    recipe = extractor._parse_ai_response(data)
    assert recipe.inferred_fields == ["servings"]


# ---------------------------------------------------------------------------
# Text extractor prompt + parsing
# ---------------------------------------------------------------------------


def test_text_prompt_flag_on_contains_inferred_fields_and_all_nine_names(flag_on):
    prompt = _text_extraction_prompt()
    assert "inferred_fields" in prompt
    for field in INFERABLE_FIELDS:
        assert field in prompt, f"text prompt must name `{field}`"


def test_text_prompt_flag_off_omits_inference_language(flag_off):
    prompt = _text_extraction_prompt()
    assert "inferred_fields" not in prompt
    assert "NEVER infer name" not in prompt
    assert "Field-level inference" not in prompt


def test_text_prompt_flag_off_keeps_original_null_rule(flag_off):
    prompt = _text_extraction_prompt()
    assert "Set missing fields to null rather than guessing" in prompt


def test_text_extractor_parses_inferred_fields():
    data = {
        "name": "Test",
        "ingredients": [],
        "inferred_fields": ["prep_time_minutes", "cuisine"],
    }
    recipe = _parse_text_response(data)
    assert recipe.inferred_fields == ["prep_time_minutes", "cuisine"]


def test_text_extractor_missing_inferred_fields_defaults_to_empty():
    data = {"name": "Test", "ingredients": []}
    recipe = _parse_text_response(data)
    assert recipe.inferred_fields == []


# ---------------------------------------------------------------------------
# Vision extractor prompt + parsing
# ---------------------------------------------------------------------------


def test_vision_prompt_flag_on_contains_inferred_fields_and_all_nine_names(flag_on):
    prompt = _vision_system_prompt()
    assert "inferred_fields" in prompt
    for field in INFERABLE_FIELDS:
        assert field in prompt, f"vision prompt must name `{field}`"


def test_vision_prompt_flag_on_preserves_ocr_disambiguation_instruction(
    flag_on,
):
    # The pre-existing "infer from context when characters are unclear"
    # is OCR disambiguation — not field-level inference. Must stay
    # verbatim when the flag is on.
    prompt = _vision_system_prompt()
    assert "infer from context when characters are unclear" in prompt


def test_vision_prompt_flag_off_omits_inference_language(flag_off):
    prompt = _vision_system_prompt()
    assert "inferred_fields" not in prompt
    assert "NEVER infer name" not in prompt
    assert "Field-level inference" not in prompt


def test_vision_prompt_flag_off_keeps_include_phrase(flag_off):
    prompt = _vision_system_prompt()
    # Narrow substring — the flag-off include rule is a single
    # sentence. The AC just requires "prior 'Only include present'
    # phrasing is intact" — i.e. the rule is still there, not the
    # exact wording.
    assert "Only include fields you can find in the image" in prompt


def test_vision_extractor_parses_inferred_fields():
    data = {
        "name": "Test",
        "ingredients": [],
        "inferred_fields": ["servings", "description"],
    }
    recipe = _parse_vision_response(data)
    assert recipe.inferred_fields == ["servings", "description"]


def test_vision_extractor_missing_inferred_fields_defaults_to_empty():
    data = {"name": "Test", "ingredients": []}
    recipe = _parse_vision_response(data)
    assert recipe.inferred_fields == []


# ---------------------------------------------------------------------------
# Dataclass + schema regression
# ---------------------------------------------------------------------------


def test_extracted_recipe_default_inferred_fields_is_empty():
    # Regression: existing construction sites that don't pass
    # ``inferred_fields`` must continue to work with a default of [].
    recipe = ExtractedRecipe(name="Test")
    assert recipe.inferred_fields == []


def test_json_ld_inferred_fields_is_empty_without_flag_influence():
    # efi-2: json_ld.py is untouched — its ExtractedRecipe always has
    # inferred_fields=[] regardless of flag state. Import and exercise
    # the parse path directly.
    from utils.services.recipe_extractors.json_ld import JsonLdExtractor

    extractor = JsonLdExtractor()
    recipe = extractor._parse_recipe_data(
        {
            "@type": "Recipe",
            "name": "Test",
            "recipeIngredient": ["1 cup flour"],
            "recipeInstructions": "Mix and bake.",
        }
    )
    assert recipe.inferred_fields == []
