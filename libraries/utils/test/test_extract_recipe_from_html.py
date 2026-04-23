"""eri-3a/3b: parse-pass invocation + IngredientFieldCoverage audit from
``RecipeExtractorRegistry.extract``.

We drive the registry's ``extract()`` through ``extract_recipe_from_html``
on hand-rolled HTML that carries a JSON-LD block. The OpenAI client is
mocked so the parse pass never reaches the network. Audit emissions
are intercepted via monkeypatch.

Covered:

* clove regression — ``"1 clove garlic, minced"`` parses cleanly.
* gram regression — ``"300 gram of vinegar"`` parses cleanly.
* range rule — ``"1-2 cups water"`` → q=1, notes="to 2 cups".
* Mixed-structure JSON-LD (2 structured + 3 text-only) — eri-3b: only
  the text-only subset goes through the parse pass; structured rows
  are preserved verbatim and order is maintained.
* All-structured JSON-LD — parse pass doesn't fire; still audits as
  ``json_ld``.
* Flag off — parse pass doesn't fire; audits as ``json_ld``.
* AI-extractor fallback path — emits coverage audit as ``ai_extractor``.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from utils.services.recipe_extractors import (
    RecipeExtractorRegistry,
    extract_recipe_from_html,
)
from utils.services.recipe_extractors.base import ExtractedIngredient


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _jsonld_html(ingredients: list[str], *, name: str = "Test Recipe") -> str:
    """Build minimal HTML with a Schema.org Recipe JSON-LD block.

    Ingredients come through as the plain-string list Schema.org
    defines — which is exactly the text-only case the parse pass
    exists to rescue.
    """
    data = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": name,
        "recipeIngredient": ingredients,
        "recipeInstructions": "Mix well.",
    }
    return f"""<html><head>
    <script type="application/ld+json">{json.dumps(data)}</script>
    </head><body><h1>{name}</h1></body></html>"""


def _build_parse_response(items: list[dict], *, total_tokens: int = 80):
    """MagicMock-ready OpenAI ChatCompletion response shape."""
    content = json.dumps({"ingredients": items})
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    usage = SimpleNamespace(total_tokens=total_tokens)
    return SimpleNamespace(choices=[choice], usage=usage)


@pytest.fixture
def capture_coverage(monkeypatch):
    """Intercept IngredientFieldCoverage audit calls."""
    calls: list[dict] = []

    def _record(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        "utils.services.recipe_extractors.log_ingredient_field_coverage",
        _record,
    )
    return calls


@pytest.fixture(autouse=True)
def silence_parse_audit(monkeypatch):
    """Audit helpers write to the DB; intercept both so tests don't
    need a live DATABASE_URL."""
    monkeypatch.setattr(
        "utils.services.recipe_extractors.ingredient_parse.log_ingredient_parse_failure",
        lambda **_: None,
    )
    monkeypatch.setattr(
        "utils.services.recipe_extractors.ingredient_parse.log_ingredient_parse_pathological",
        lambda **_: None,
    )


@pytest.fixture
def fresh_registry(monkeypatch):
    """Reset the module-level singleton registry so each test starts
    clean. Required because the default registry caches its AIExtractor
    (and its mock openai client) across tests."""
    monkeypatch.setattr(
        "utils.services.recipe_extractors._default_registry", None
    )
    yield
    monkeypatch.setattr(
        "utils.services.recipe_extractors._default_registry", None
    )


# ---------------------------------------------------------------------------
# Happy-path regression fixtures
# ---------------------------------------------------------------------------


def test_clove_regression_parses_from_json_ld(fresh_registry, capture_coverage):
    html = _jsonld_html(
        [
            "1 clove garlic, minced",
            "2 tbsp olive oil",
            "1/2 tsp salt",
        ]
    )
    client = MagicMock()
    client.chat.completions.create.return_value = _build_parse_response(
        [
            {"quantity": 1, "unit": "clove", "name": "garlic", "notes": "minced"},
            {"quantity": 2, "unit": "tbsp", "name": "olive oil", "notes": None},
            {"quantity": 0.5, "unit": "tsp", "name": "salt", "notes": None},
        ]
    )

    result = extract_recipe_from_html(html, url="https://example.com/clove", openai_client=client)
    assert result.success
    ings = result.recipe.ingredients
    assert len(ings) == 3
    assert ings[0].quantity == 1
    assert ings[0].unit == "clove"
    assert ings[0].name == "garlic"
    assert ings[0].notes == "minced"
    # One coverage audit row for the json_ld_parse_pass source.
    assert len(capture_coverage) == 1
    assert capture_coverage[0]["source"] == "json_ld_parse_pass"
    assert capture_coverage[0]["total"] == 3
    assert capture_coverage[0]["qty_present"] == 3
    assert capture_coverage[0]["unit_present"] == 3
    assert capture_coverage[0]["url_host"] == "example.com"


def test_gram_regression_parses_from_json_ld(fresh_registry, capture_coverage):
    html = _jsonld_html(["300 gram of vinegar"])
    client = MagicMock()
    client.chat.completions.create.return_value = _build_parse_response(
        [{"quantity": 300, "unit": "g", "name": "vinegar", "notes": None}]
    )

    result = extract_recipe_from_html(html, url="https://a.test/", openai_client=client)
    assert result.success
    assert result.recipe.ingredients[0].quantity == 300
    assert result.recipe.ingredients[0].unit == "g"
    assert result.recipe.ingredients[0].name == "vinegar"
    assert capture_coverage[0]["source"] == "json_ld_parse_pass"


def test_range_regression_q1_notes_to2cups(fresh_registry, capture_coverage):
    html = _jsonld_html(["1-2 cups water"])
    client = MagicMock()
    client.chat.completions.create.return_value = _build_parse_response(
        [{"quantity": 1, "unit": "cup", "name": "water", "notes": "to 2 cups"}]
    )

    result = extract_recipe_from_html(html, url="https://example.com/", openai_client=client)
    ing = result.recipe.ingredients[0]
    assert ing.quantity == 1
    assert ing.unit == "cup"
    assert ing.notes == "to 2 cups"


# ---------------------------------------------------------------------------
# Mixed-structure (eri-3b)
# ---------------------------------------------------------------------------


def test_mixed_structure_only_text_only_strings_are_sent_to_openai(
    fresh_registry, capture_coverage
):
    """eri-3b — the parse-pass OpenAI call must see ONLY the text-only
    strings, never the structured rows. Stress: 3 structured + 2
    text-only interleaved."""
    registry = RecipeExtractorRegistry()
    client = MagicMock()
    client.chat.completions.create.return_value = _build_parse_response(
        [
            {"quantity": 1, "unit": "clove", "name": "garlic", "notes": None},
            {"quantity": 2, "unit": "stalk", "name": "celery", "notes": None},
        ]
    )
    registry._ai_extractor._client = client

    html = _jsonld_html(
        [
            "A",
            "1 clove garlic",
            "B",
            "C",
            "2 stalks celery",
        ]
    )
    raw_result = registry._extractors[0].extract(html, url="https://ex.com/")
    # Overwrite indices 0, 2, 3 with structured rows (A, B, C stay
    # structured-only with distinct text markers).
    raw_result.recipe.ingredients[0] = ExtractedIngredient(
        text="A", quantity=1, unit="cup", name="A"
    )
    raw_result.recipe.ingredients[2] = ExtractedIngredient(
        text="B", quantity=1, unit="cup", name="B"
    )
    raw_result.recipe.ingredients[3] = ExtractedIngredient(
        text="C", quantity=1, unit="cup", name="C"
    )

    from utils.services.recipe_extractors import (
        _apply_parse_pass,
        _emit_coverage_audit,
    )

    source = _apply_parse_pass(
        raw_result.recipe, openai_client=client, url="https://ex.com/"
    )
    _emit_coverage_audit(raw_result.recipe, source=source, url="https://ex.com/")

    # Exactly one parse-pass call
    assert client.chat.completions.create.call_count == 1
    prompt = client.chat.completions.create.call_args.kwargs["messages"][1][
        "content"
    ]
    # The prompt body numbers its inputs "1. ...\n2. ..." — assert the
    # text-only strings are present, the structured-row strings are NOT.
    assert "1 clove garlic" in prompt
    assert "2 stalks celery" in prompt
    assert "\nA\n" not in prompt and "1. A\n" not in prompt
    assert "\nB\n" not in prompt and "2. B\n" not in prompt
    assert "\nC\n" not in prompt

    ings = raw_result.recipe.ingredients
    # Structured rows kept verbatim
    assert ings[0].name == "A"
    assert ings[2].name == "B"
    assert ings[3].name == "C"
    # Text-only rows filled in
    assert ings[1].unit == "clove"
    assert ings[4].unit == "stalk"
    assert source == "json_ld_parse_pass"


def test_mixed_structure_preserves_structured_rows_and_splices_back_in_order(
    fresh_registry, capture_coverage
):
    """Schema.org allows HowToSupply objects with structured fields. We
    simulate the shape that produces mixed-structure results: inject the
    structured rows directly into the recipe's ingredients list AFTER
    extraction so the test exercises only the subset-filter + splice,
    not the JSON-LD parser itself.
    """
    registry = RecipeExtractorRegistry()
    client = MagicMock()
    client.chat.completions.create.return_value = _build_parse_response(
        [
            {"quantity": 1, "unit": "clove", "name": "garlic", "notes": "minced"},
            {"quantity": 300, "unit": "g", "name": "vinegar", "notes": None},
            {"quantity": 2, "unit": "stalk", "name": "celery", "notes": "chopped"},
        ]
    )
    registry._ai_extractor._client = client

    html = _jsonld_html(
        [
            "1 clove garlic, minced",  # text-only #0
            "2 tbsp olive oil",         # text-only #1 but we'll overwrite with structured
            "300 gram of vinegar",      # text-only #2
            "1 tsp cumin",              # text-only #3 but we'll overwrite with structured
            "2 stalks celery, chopped", # text-only #4
        ]
    )
    # Run the registry's can_extract/extract directly so we can mutate the
    # recipe BEFORE the parse pass — matching the "structured rows came
    # straight from JSON-LD" scenario.
    json_ld = registry._extractors[0]
    raw_result = json_ld.extract(html, url="https://example.com/")
    assert raw_result.success
    # Simulate 2 of the 5 rows already being structured (indices 1 and 3).
    raw_result.recipe.ingredients[1] = ExtractedIngredient(
        text="2 tbsp olive oil",
        quantity=2,
        unit="tbsp",
        name="olive oil",
    )
    raw_result.recipe.ingredients[3] = ExtractedIngredient(
        text="1 tsp cumin",
        quantity=1,
        unit="tsp",
        name="cumin",
    )

    # Drive the subset filter + splice via the internal helper.
    from utils.services.recipe_extractors import (
        _apply_parse_pass,
        _emit_coverage_audit,
    )

    source = _apply_parse_pass(
        raw_result.recipe, openai_client=client, url="https://example.com/"
    )
    _emit_coverage_audit(raw_result.recipe, source=source, url="https://example.com/")

    ings = raw_result.recipe.ingredients
    assert len(ings) == 5
    # Text-only indices (0, 2, 4) got parsed
    assert ings[0].name == "garlic"
    assert ings[0].unit == "clove"
    assert ings[2].name == "vinegar"
    assert ings[2].unit == "g"
    assert ings[4].name == "celery"
    assert ings[4].unit == "stalk"
    # Structured rows (1, 3) are untouched
    assert ings[1].name == "olive oil"
    assert ings[1].unit == "tbsp"
    assert ings[3].name == "cumin"
    assert ings[3].unit == "tsp"
    # Parse pass called exactly once with 3 strings (the text-only subset).
    assert client.chat.completions.create.call_count == 1
    assert source == "json_ld_parse_pass"
    assert capture_coverage[0]["source"] == "json_ld_parse_pass"
    assert capture_coverage[0]["total"] == 5


# ---------------------------------------------------------------------------
# All-structured / empty-subset short-circuits
# ---------------------------------------------------------------------------


def test_all_structured_json_ld_does_not_fire_parse_pass(
    fresh_registry, capture_coverage
):
    """If every ingredient already has qty/unit/name, the parse pass is
    a no-op and coverage audit marks the source as ``json_ld``."""
    html = _jsonld_html(["1 cup flour"])
    client = MagicMock()
    # If the parse pass is called, it would explode here.
    client.chat.completions.create.side_effect = AssertionError("should not fire")

    from utils.services.recipe_extractors import (
        _apply_parse_pass,
        _emit_coverage_audit,
    )

    registry = RecipeExtractorRegistry()
    raw_result = registry._extractors[0].extract(html, url="https://ex.com/")
    # Pre-fill all ingredients so none is text-only.
    for ing in raw_result.recipe.ingredients:
        ing.quantity = 1
        ing.unit = "cup"
        ing.name = "flour"

    source = _apply_parse_pass(
        raw_result.recipe, openai_client=client, url="https://ex.com/"
    )
    _emit_coverage_audit(raw_result.recipe, source=source, url="https://ex.com/")

    assert source == "json_ld"
    assert capture_coverage[0]["source"] == "json_ld"


def test_parse_pass_flag_off_does_not_fire(
    monkeypatch, fresh_registry, capture_coverage
):
    monkeypatch.setenv("EXTRACTOR_JSON_LD_INGREDIENT_PARSE", "false")
    html = _jsonld_html(["1 clove garlic, minced"])
    client = MagicMock()
    client.chat.completions.create.side_effect = AssertionError("should not fire")

    result = extract_recipe_from_html(
        html, url="https://ex.com/", openai_client=client
    )
    assert result.success
    # Parse pass was flag-gated off — ingredient stays text-only.
    ing = result.recipe.ingredients[0]
    assert ing.quantity is None
    assert ing.unit is None
    assert ing.name is None
    assert capture_coverage[0]["source"] == "json_ld"


# ---------------------------------------------------------------------------
# AI-fallback path — coverage audit still emits
# ---------------------------------------------------------------------------


def test_ai_fallback_path_audits_as_ai_extractor(
    fresh_registry, capture_coverage
):
    """No JSON-LD block → AI extractor fires. Coverage audit runs with
    source=``ai_extractor``; no parse pass."""
    html = "<html><body>just prose, no structured data at all, but long enough to get past the AI extractor's length guard...</body></html>" * 5
    client = MagicMock()
    ai_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=json.dumps(
                        {
                            "recipes": [
                                {
                                    "name": "Prose Cake",
                                    "ingredients": [
                                        {
                                            "text": "flour",
                                            "quantity": 2,
                                            "unit": "cup",
                                            "name": "flour",
                                        }
                                    ],
                                    "instructions": "Bake.",
                                }
                            ]
                        }
                    )
                )
            )
        ],
        usage=SimpleNamespace(total_tokens=100),
    )
    client.chat.completions.create.return_value = ai_response

    result = extract_recipe_from_html(html, openai_client=client)
    assert result.success
    assert result.extractor_used == "ai"
    assert capture_coverage[0]["source"] == "ai_extractor"


# ---------------------------------------------------------------------------
# Audit emission edge cases
# ---------------------------------------------------------------------------


def test_no_coverage_audit_when_no_ingredients(fresh_registry, capture_coverage):
    """Degenerate JSON-LD with empty recipeIngredient — no audit emission."""
    html = _jsonld_html([])
    client = MagicMock()
    result = extract_recipe_from_html(html, url="https://ex.com/", openai_client=client)
    assert result.success
    # No ingredients → no coverage emission → recipe may not even have a
    # meaningful coverage row.
    assert capture_coverage == []


def test_coverage_audit_contains_url_host(fresh_registry, capture_coverage):
    html = _jsonld_html(["1 cup flour"])
    client = MagicMock()
    client.chat.completions.create.return_value = _build_parse_response(
        [{"quantity": 1, "unit": "cup", "name": "flour", "notes": None}]
    )
    extract_recipe_from_html(
        html, url="https://www.seriouseats.com/recipes/foo", openai_client=client
    )
    assert capture_coverage[0]["url_host"] == "www.seriouseats.com"


def test_coverage_audit_tolerates_null_url(fresh_registry, capture_coverage):
    html = _jsonld_html(["1 cup flour"])
    client = MagicMock()
    client.chat.completions.create.return_value = _build_parse_response(
        [{"quantity": 1, "unit": "cup", "name": "flour", "notes": None}]
    )
    extract_recipe_from_html(html, url=None, openai_client=client)
    assert capture_coverage[0]["url_host"] is None
