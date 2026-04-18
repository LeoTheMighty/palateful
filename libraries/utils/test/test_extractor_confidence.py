"""irrd-3: confidence score end-to-end (heuristic + prompt flag + resolve).

No network I/O — every extractor path is exercised through its post-parse
method with pre-baked response payloads, so the tests run without an
OPENAI_API_KEY and without any LLM spend. The eval-calibration gate
(AC8-AC11) is deferred to irrd-3a.
"""

from __future__ import annotations

import pytest

from utils.services.recipe_extractors.ai_extractor import AIExtractor
from utils.services.recipe_extractors.base import (
    ExtractedIngredient,
    ExtractedRecipe,
)
from utils.services.recipe_extractors.confidence_heuristic import (
    compute_heuristic_confidence,
    normalize_model_confidence,
    resolve_confidence,
)
from utils.services.recipe_extractors.confidence_prompt import (
    confidence_rule,
    emit_confidence,
)
from utils.services.recipe_extractors.json_ld import JsonLdExtractor
from utils.services.recipe_extractors.text_extractor import _parse_response as text_parse
from utils.services.recipe_extractors.vision_extractor import _parse_response as vision_parse


@pytest.fixture
def flag_off(monkeypatch):
    monkeypatch.setenv("EXTRACTOR_EMIT_CONFIDENCE", "false")


@pytest.fixture
def flag_on(monkeypatch):
    monkeypatch.setenv("EXTRACTOR_EMIT_CONFIDENCE", "true")


@pytest.fixture
def flag_unset(monkeypatch):
    monkeypatch.delenv("EXTRACTOR_EMIT_CONFIDENCE", raising=False)


# ---------------------------------------------------------------------------
# Flag parsing (AC10)
# ---------------------------------------------------------------------------


def test_emit_confidence_default_on(flag_unset):
    assert emit_confidence() is True


@pytest.mark.parametrize("value", ["false", "FALSE", "0", "no", "off"])
def test_emit_confidence_off_values(monkeypatch, value):
    monkeypatch.setenv("EXTRACTOR_EMIT_CONFIDENCE", value)
    assert emit_confidence() is False


@pytest.mark.parametrize("value", ["true", "1", "yes", "on", "anything"])
def test_emit_confidence_truthy_values(monkeypatch, value):
    monkeypatch.setenv("EXTRACTOR_EMIT_CONFIDENCE", value)
    assert emit_confidence() is True


def test_confidence_rule_when_off_is_empty(flag_off):
    assert confidence_rule() == ""


def test_confidence_rule_when_on_mentions_both_keys(flag_on):
    rule = confidence_rule()
    assert "confidence_score" in rule
    assert "confidence_source" in rule
    assert "model" in rule


# ---------------------------------------------------------------------------
# normalize_model_confidence
# ---------------------------------------------------------------------------


def test_normalize_accepts_valid_floats():
    assert normalize_model_confidence(0.0) == 0.0
    assert normalize_model_confidence(0.5) == 0.5
    assert normalize_model_confidence(1.0) == 1.0


def test_normalize_accepts_numeric_strings():
    assert normalize_model_confidence("0.42") == 0.42


def test_normalize_rejects_out_of_range():
    assert normalize_model_confidence(1.5) is None
    assert normalize_model_confidence(-0.1) is None
    assert normalize_model_confidence("2.0") is None


def test_normalize_rejects_garbage():
    assert normalize_model_confidence("not a number") is None
    assert normalize_model_confidence(None) is None
    assert normalize_model_confidence(True) is None  # bool is not valid
    assert normalize_model_confidence([0.5]) is None


def test_normalize_rejects_nan():
    assert normalize_model_confidence(float("nan")) is None


# ---------------------------------------------------------------------------
# compute_heuristic_confidence — AC7 deterministic fixture
# ---------------------------------------------------------------------------


def test_heuristic_matches_canonical_fixture():
    """AC7: 3 ingredients with quantity + title + 4 steps -> 0.967.

    With all three signals saturated:
      0.4 * (3/3) + 0.3 * 1.0 + 0.3 * min(4/3, 1.0) = 0.4 + 0.3 + 0.3 = 1.0
    When only 2 of 3 ingredients have quantity:
      0.4 * (2/3) + 0.3 * 1.0 + 0.3 * 1.0 = 0.2667 + 0.6 = 0.8667
    """
    recipe = ExtractedRecipe(
        name="Test Recipe",
        ingredients=[
            ExtractedIngredient(text="flour", quantity=2.0, unit="cup"),
            ExtractedIngredient(text="eggs", quantity=3.0, unit=None),
            ExtractedIngredient(text="salt", quantity=None, unit=None),
        ],
        instructions="1. Mix.\n2. Bake.\n3. Cool.\n4. Serve.",
    )
    # No structured steps; heuristic uses instructions lines as proxy.
    score = compute_heuristic_confidence(recipe)
    assert round(score, 3) == 0.867


def test_heuristic_all_saturated_is_one():
    recipe = ExtractedRecipe(
        name="Full Recipe",
        ingredients=[
            ExtractedIngredient(text="a", quantity=1.0),
            ExtractedIngredient(text="b", quantity=2.0),
        ],
        instructions="one\ntwo\nthree",
    )
    assert round(compute_heuristic_confidence(recipe), 3) == 1.0


def test_heuristic_empty_recipe_floors_at_zero():
    recipe = ExtractedRecipe(name="Untitled Recipe", ingredients=[])
    assert compute_heuristic_confidence(recipe) == 0.0


def test_heuristic_accepts_dict_form():
    data = {
        "name": "From Dict",
        "ingredients": [{"quantity": 1}, {"quantity": None}],
        "instructions": "only one line",
    }
    score = compute_heuristic_confidence(data)
    assert 0.0 < score <= 1.0


def test_heuristic_bool_quantity_not_counted():
    """Pydantic/JSON round-trips can stash `true` where a number belongs;
    those must not be counted as a real quantity."""
    recipe = ExtractedRecipe(
        name="X",
        ingredients=[ExtractedIngredient(text="a", quantity=True)],  # type: ignore[arg-type]
        instructions="1. go",
    )
    # Title present, 1 step, 0 valid quantities → 0.3 + 0.3*(1/3) = 0.4
    assert round(compute_heuristic_confidence(recipe), 3) == 0.4


# ---------------------------------------------------------------------------
# resolve_confidence — the entry point extractors call
# ---------------------------------------------------------------------------


def test_resolve_prefers_model_when_flag_on(flag_on):
    recipe = ExtractedRecipe(name="R", ingredients=[], instructions="step")
    score, source = resolve_confidence({"confidence_score": 0.73}, recipe)
    assert score == 0.73
    assert source == "model"


def test_resolve_preserves_zero_as_model_signal(flag_on):
    """0.0 is a legitimate model output — must not fall through to heuristic."""
    recipe = ExtractedRecipe(name="R", ingredients=[], instructions="step")
    score, source = resolve_confidence({"confidence_score": 0.0}, recipe)
    assert score == 0.0
    assert source == "model"


def test_resolve_falls_back_on_null_score(flag_on):
    recipe = ExtractedRecipe(
        name="R",
        ingredients=[ExtractedIngredient(text="x", quantity=1.0)],
        instructions="1. a\n2. b\n3. c",
    )
    score, source = resolve_confidence({"confidence_score": None}, recipe)
    assert source == "heuristic"
    assert score > 0.0


def test_resolve_falls_back_on_malformed_score(flag_on):
    recipe = ExtractedRecipe(
        name="R",
        ingredients=[ExtractedIngredient(text="x", quantity=1.0)],
        instructions="1. a",
    )
    score, source = resolve_confidence({"confidence_score": "not numeric"}, recipe)
    assert source == "heuristic"
    assert 0.0 <= score <= 1.0


def test_resolve_always_heuristic_when_flag_off(flag_off):
    """AC10 rollback path: flag off means the prompt never asked, so the
    model's response wouldn't carry the key. Explicitly gate on the flag
    so even a model that emitted one gets ignored."""
    recipe = ExtractedRecipe(
        name="R",
        ingredients=[ExtractedIngredient(text="x", quantity=1.0)],
        instructions="1. a",
    )
    score, source = resolve_confidence({"confidence_score": 0.99}, recipe)
    assert source == "heuristic"
    # Heuristic signal: title + 1/1 ingredient qty + 1/3 steps = 1.0 + 0.4 + 0.1 = 0.4 + 0.3 + 0.1 = 0.8
    # (0.4*1 + 0.3*1 + 0.3*(1/3))
    assert round(score, 3) == 0.8


# ---------------------------------------------------------------------------
# Per-extractor _parse_response paths (AC2, AC3, AC4)
# ---------------------------------------------------------------------------


def test_ai_extractor_parse_surfaces_model_confidence(flag_on):
    ext = AIExtractor()
    recipe = ext._parse_ai_response(  # noqa: SLF001
        {
            "name": "Cookie",
            "ingredients": [
                {"text": "flour", "quantity": 2, "unit": "cup"},
                {"text": "sugar", "quantity": 1, "unit": "cup"},
            ],
            "instructions": "Mix. Bake.",
            "confidence_score": 0.91,
            "confidence_source": "model",
        },
        url=None,
    )
    assert recipe.confidence_score == 0.91
    assert recipe.confidence_source == "model"


def test_ai_extractor_parse_falls_back_when_missing(flag_on):
    ext = AIExtractor()
    recipe = ext._parse_ai_response(  # noqa: SLF001
        {
            "name": "Cookie",
            "ingredients": [
                {"text": "flour", "quantity": 2, "unit": "cup"},
                {"text": "sugar", "quantity": 1, "unit": "cup"},
            ],
            "instructions": "1. Mix.\n2. Bake.",
        },
        url=None,
    )
    assert recipe.confidence_source == "heuristic"
    assert 0.0 <= recipe.confidence_score <= 1.0


def test_text_extractor_parse_surfaces_model_confidence(flag_on):
    recipe = text_parse(
        {
            "name": "Bread",
            "ingredients": [{"text": "flour", "quantity": 3, "unit": "cup"}],
            "steps": [{"order": 1, "instruction": "Knead."}],
            "confidence_score": 0.62,
            "confidence_source": "model",
        }
    )
    assert recipe.confidence_score == 0.62
    assert recipe.confidence_source == "model"


def test_vision_extractor_parse_falls_back_on_out_of_range(flag_on):
    recipe = vision_parse(
        {
            "name": "Pie",
            "ingredients": [{"text": "apples", "quantity": 4}],
            "instructions": "1. Bake.",
            "confidence_score": 1.5,  # garbage
        }
    )
    assert recipe.confidence_source == "heuristic"


def test_json_ld_deterministic_confidence_full():
    ext = JsonLdExtractor()
    html = """<html><script type="application/ld+json">
    {"@type": "Recipe", "name": "Pie",
     "recipeIngredient": ["2 cups flour"],
     "recipeInstructions": "Mix and bake"}
    </script></html>"""
    result = ext.extract(html)
    assert result.success
    assert result.recipe is not None
    assert result.recipe.confidence_score == 1.0
    assert result.recipe.confidence_source == "model"


def test_json_ld_deterministic_confidence_partial():
    ext = JsonLdExtractor()
    # Title only — no ingredients, no instructions.
    html = """<html><script type="application/ld+json">
    {"@type": "Recipe", "name": "Just a title"}
    </script></html>"""
    result = ext.extract(html)
    assert result.success
    assert result.recipe is not None
    # 1 of 3 signals -> 1/3, but floor is 0.3
    assert result.recipe.confidence_score == pytest.approx(1 / 3, abs=0.01)
    assert result.recipe.confidence_source == "model"


# ---------------------------------------------------------------------------
# Extractor prompt content (AC2 + AC10)
# ---------------------------------------------------------------------------


def test_ai_prompt_contains_confidence_instruction_when_on(flag_on):
    from utils.services.recipe_extractors import ai_extractor as mod

    prompt = mod._extraction_prompt()  # noqa: SLF001
    assert "confidence_score" in prompt
    assert "confidence_source" in prompt


def test_ai_prompt_omits_confidence_instruction_when_off(flag_off):
    from utils.services.recipe_extractors import ai_extractor as mod

    prompt = mod._extraction_prompt()  # noqa: SLF001
    assert "confidence_score" not in prompt


def test_text_prompt_omits_confidence_when_off(flag_off):
    from utils.services.recipe_extractors import text_extractor as mod

    prompt = mod._text_extraction_prompt()  # noqa: SLF001
    assert "confidence_score" not in prompt


def test_vision_prompt_omits_confidence_when_off(flag_off):
    from utils.services.recipe_extractors import vision_extractor as mod

    prompt = mod._vision_system_prompt()  # noqa: SLF001
    assert "confidence_score" not in prompt
