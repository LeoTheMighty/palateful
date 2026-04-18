"""Tests for the `ExtractionResult.recipes` array contract (bugs-imp-pho-1).

Every extractor must populate `result.recipes` as a list. Single-recipe
inputs produce a length-1 list. Multi-recipe inputs produce N entries.
The deprecated `result.recipe` alias continues to resolve to
`recipes[0]` via `ExtractionResult.__post_init__`.
"""

import json
from unittest.mock import MagicMock

import pytest

from utils.services.recipe_extractors.ai_extractor import AIExtractor
from utils.services.recipe_extractors.base import (
    ExtractedRecipe,
    ExtractionResult,
)
from utils.services.recipe_extractors.json_ld import JsonLdExtractor
from utils.services.recipe_extractors.text_extractor import (
    extract_recipe_from_text,
)
from utils.services.recipe_extractors.vision_extractor import (
    extract_recipe_from_image,
)


# ---------- base.py sync ----------


def test_extraction_result_sync_from_recipe_to_recipes():
    r = ExtractedRecipe(name="Cake")
    result = ExtractionResult(success=True, recipe=r)
    assert result.recipes == [r]
    assert result.recipe is r


def test_extraction_result_sync_from_recipes_to_recipe_alias():
    r1 = ExtractedRecipe(name="A")
    r2 = ExtractedRecipe(name="B")
    result = ExtractionResult(success=True, recipes=[r1, r2])
    assert result.recipe is r1  # alias to first
    assert len(result.recipes) == 2


def test_extraction_result_empty_when_failure():
    result = ExtractionResult(success=False, error_code="X")
    assert result.recipes == []
    assert result.recipe is None


# ---------- mock openai helper ----------


def _make_openai_mock(payload: dict | str, total_tokens: int = 100) -> MagicMock:
    """Return a mock OpenAI client whose chat.completions.create returns
    a response with the given JSON payload as content.
    """
    content = payload if isinstance(payload, str) else json.dumps(payload)
    mock = MagicMock()
    mock.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=content))],
        usage=MagicMock(total_tokens=total_tokens),
    )
    return mock


# ---------- text_extractor ----------


def test_text_extractor_single_recipe_array():
    """New multi-recipe shape with one recipe → length-1 recipes list."""
    payload = {
        "recipes": [
            {
                "name": "Chocolate Chip Cookies",
                "ingredients": [{"text": "flour", "quantity": 2, "unit": "cups"}],
                "steps": [{"order": 1, "instruction": "Mix."}],
            }
        ]
    }
    client = _make_openai_mock(payload)
    result = extract_recipe_from_text("some OCR text long enough to pass", client)
    assert result.success
    assert len(result.recipes) == 1
    assert result.recipes[0].name == "Chocolate Chip Cookies"
    # Legacy alias still works.
    assert result.recipe.name == "Chocolate Chip Cookies"


def test_text_extractor_multi_recipe_array():
    """Two recipes in the array → two ExtractedRecipe entries."""
    payload = {
        "recipes": [
            {"name": "Recipe A", "ingredients": []},
            {"name": "Recipe B", "ingredients": []},
        ]
    }
    client = _make_openai_mock(payload)
    result = extract_recipe_from_text("some OCR text long enough to pass", client)
    assert result.success
    assert [r.name for r in result.recipes] == ["Recipe A", "Recipe B"]


def test_text_extractor_bare_object_fallback():
    """Model returns a bare recipe (no "recipes" key) → wrap in length-1."""
    payload = {
        "name": "Fallback Recipe",
        "ingredients": [{"text": "salt"}],
    }
    client = _make_openai_mock(payload)
    result = extract_recipe_from_text("some OCR text long enough to pass", client)
    assert result.success
    assert len(result.recipes) == 1
    assert result.recipes[0].name == "Fallback Recipe"


def test_text_extractor_malformed_json_fails():
    """Malformed JSON → success=False with AI_JSON_PARSE_ERROR."""
    client = _make_openai_mock("{not valid json")
    result = extract_recipe_from_text("some OCR text long enough to pass", client)
    assert not result.success
    assert result.error_code == "AI_JSON_PARSE_ERROR"
    assert result.recipes == []


def test_text_extractor_empty_recipes_array_fails():
    """Empty recipes array → success=False."""
    client = _make_openai_mock({"recipes": []})
    result = extract_recipe_from_text("some OCR text long enough to pass", client)
    assert not result.success
    assert result.error_code == "AI_NO_RECIPE_FOUND"


# ---------- vision_extractor ----------


def test_vision_extractor_multi_recipe_array():
    payload = {
        "recipes": [
            {"name": "Vision A", "ingredients": []},
            {"name": "Vision B", "ingredients": []},
        ]
    }
    client = _make_openai_mock(payload)
    # Raw bytes OK — we just need the call path
    result = extract_recipe_from_image(b"fake-png-bytes", openai_client=client)
    assert result.success
    assert [r.name for r in result.recipes] == ["Vision A", "Vision B"]


def test_vision_extractor_bare_object_fallback():
    payload = {"name": "Single Vision Recipe", "ingredients": []}
    client = _make_openai_mock(payload)
    result = extract_recipe_from_image(b"fake-png-bytes", openai_client=client)
    assert result.success
    assert len(result.recipes) == 1
    assert result.recipes[0].name == "Single Vision Recipe"


def test_vision_extractor_single_recipe_array():
    payload = {"recipes": [{"name": "Solo Vision", "ingredients": []}]}
    client = _make_openai_mock(payload)
    result = extract_recipe_from_image(b"fake-png-bytes", openai_client=client)
    assert result.success
    assert len(result.recipes) == 1
    assert result.recipes[0].name == "Solo Vision"


# ---------- ai_extractor (URL/HTML) ----------


def test_ai_extractor_multi_recipe_array():
    payload = {
        "recipes": [
            {"name": "Page Recipe A", "ingredients": []},
            {"name": "Page Recipe B", "ingredients": []},
        ]
    }
    client = _make_openai_mock(payload)
    ai = AIExtractor(openai_client=client)
    # Needs enough text to pass can_extract()
    result = ai.extract("<html>" + "x" * 200 + "</html>", url="https://example.com/r")
    assert result.success
    assert [r.name for r in result.recipes] == ["Page Recipe A", "Page Recipe B"]


def test_ai_extractor_bare_object_fallback():
    payload = {"name": "HTML Recipe", "ingredients": []}
    client = _make_openai_mock(payload)
    ai = AIExtractor(openai_client=client)
    result = ai.extract("<html>" + "x" * 200 + "</html>", url="https://example.com/r")
    assert result.success
    assert len(result.recipes) == 1
    assert result.recipes[0].name == "HTML Recipe"


# ---------- json_ld ----------


def test_json_ld_wraps_in_length_one_list():
    html = """
    <html><head>
    <script type="application/ld+json">
    {"@type": "Recipe", "name": "Test Recipe", "recipeIngredient": ["1 cup flour"]}
    </script>
    </head></html>
    """
    extractor = JsonLdExtractor()
    result = extractor.extract(html, url="https://example.com/r")
    assert result.success
    assert len(result.recipes) == 1
    assert result.recipes[0].name == "Test Recipe"
    assert result.recipe is result.recipes[0]  # alias points to first


# ---------- vision line-30 anti-instruction gone ----------


def test_vision_prompt_does_not_tell_model_to_drop_extra_recipes():
    """Regression guard for bugs-imp-pho-1: the old prompt literally said
    'extract only the primary/largest recipe' which is the opposite of FR88.
    """
    from utils.services.recipe_extractors import vision_extractor

    assert "primary/largest recipe" not in vision_extractor.VISION_SYSTEM_PROMPT
    assert "separate object in the" in vision_extractor.VISION_SYSTEM_PROMPT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
