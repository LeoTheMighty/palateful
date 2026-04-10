# Story 13.6: GPT-4o-mini Vision Track

## Status: Complete

## What Was Done

### 1. Vision Extractor Created
**File:** `libraries/utils/utils/services/recipe_extractors/vision_extractor.py`

- Standalone function `extract_recipe_from_image(image, openai_client=None)` that accepts either a `PIL.Image.Image` or raw `bytes`.
- Converts the image to base64 PNG and sends it to OpenAI's GPT-4o-mini model via the vision API (`image_url` content type with `detail: "high"`).
- Uses `response_format: {"type": "json_object"}` for reliable JSON output.
- Prompt requests the same structured recipe fields as the text and AI extractors (name, description, ingredients, instructions, servings, times, vibes, etc.).
- Parses the JSON response into `ExtractedRecipe` / `ExtractedIngredient` dataclasses matching the existing extractor pattern.
- Validates the output against the standard schema via `validate_extraction_result()` from `utils.schemas.recipe_extraction_schema`.
- Returns `ExtractionResult` with `extractor_used="vision_ai"` and cost tracking, consistent with `text_extractor.py` and `ai_extractor.py`.
- Full error handling: JSON parse errors, empty responses, "no recipe found" responses, and general exceptions.

### 2. Registered in Extractors Package
**File:** `libraries/utils/utils/services/recipe_extractors/__init__.py`

- Added `extract_recipe_from_image` import from `vision_extractor`.
- Added `extract_recipe_from_image` to the `__all__` exports list.

### 3. Design Decisions

- **Function-based pattern** (like `text_extractor.py`) rather than class-based (like `ai_extractor.py`) since vision extraction operates on images, not HTML content, and does not fit the `BaseExtractor` interface (`can_extract`/`extract` take `html_content`).
- **Not wired into the import pipeline** -- this is a standalone extractor for the eval suite to call directly.
- **Lazy OpenAI client** -- accepts an optional `openai_client` parameter for testing/dependency injection; creates a default `OpenAI()` client if none provided (picks up `OPENAI_API_KEY` from environment).
- **No `OPENAI_API_KEY`/`OPENAI_MODEL` constants imported** -- these don't exist in `utils.constants`. Instead follows the same pattern as existing extractors: default client reads the env var, model is hardcoded to `gpt-4o-mini`.

## Dependencies

- `openai ^2.8.1` -- already in `libraries/utils/pyproject.toml`
- `pillow >=11.3.0` -- already in `libraries/utils/pyproject.toml`
- `utils.schemas.recipe_extraction_schema` -- created in Story 13.4
