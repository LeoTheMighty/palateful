# Story 13.4: Standard Recipe JSON Schema & Validation

## Status: Complete

## What Was Done

### 1. Schema Validation Module Created
**File:** `libraries/utils/utils/schemas/recipe_extraction_schema.py`

- Defined `RECIPE_EXTRACTION_SCHEMA` as the canonical JSON Schema (Draft 7 compatible) that all extractors must conform to.
- Implemented `validate_extraction_result(data: dict) -> tuple[bool, list[str]]` validation function.
- Dual validation strategy: uses `jsonschema` library when available, falls back to comprehensive manual validation (required fields, type checking, nested array/object validation).
- Manual fallback covers: required fields, type unions (nullable types), nested array item validation, and nested object property type checks.

### 2. Package Init Created
**File:** `libraries/utils/utils/schemas/__init__.py`

- Exports `RECIPE_EXTRACTION_SCHEMA` and `validate_extraction_result` for clean imports.

### 3. Schema Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | Yes | Recipe name |
| `description` | string/null | No | Brief description |
| `ingredients` | array of objects | No | Each item requires `name`; optional: `quantity`, `unit`, `notes`, `is_optional` |
| `instructions` | string/null | No | Full instructions text |
| `steps` | array of objects | No | Structured steps with `instruction` and `order` |
| `prep_time_minutes` | integer/null | No | |
| `cook_time_minutes` | integer/null | No | |
| `servings` | integer/null | No | |
| `tags` | array of strings | No | |
| `source_url` | string/null | No | |
| `image_url` | string/null | No | |
| `primary_vibe` | string/null | No | |
| `secondary_vibe` | string/null | No | |

Extra fields (e.g. `author`, `cuisine`, `extractor_used`) are allowed and pass through.

## Extractor Gap Analysis

### Current Extractors Reviewed
- `text_extractor.py` -- AI extraction from OCR text
- `ai_extractor.py` -- AI extraction from HTML
- `json_ld.py` -- Structured data extraction from JSON-LD
- `pdf_extractor.py` -- PDF text/image extraction (delegates to text_extractor)
- `video_extractor.py` -- Video metadata extraction (delegates to text_extractor)
- `audio_extractor.py` -- Audio transcription (delegates to text_extractor)

### Gap 1: Ingredient `name` Field May Be Null
**Severity:** Medium
**Details:** The schema requires `name` on each ingredient object. However, the `JsonLdExtractor` creates `ExtractedIngredient` with only `text` populated (the `name` field defaults to `None`). When serialized to dict in `extract_recipe_task.py`, this produces `{"name": null, ...}` which would fail validation.
**Affected extractors:** `json_ld.py`
**Fix needed:** JSON-LD extractor should attempt to parse ingredient name from the text, or `name` should fall back to `text` during serialization.

### Gap 2: No `steps` Field Currently Produced
**Severity:** Low
**Details:** No extractor currently outputs the `steps` array (structured `{instruction, order}` objects). All extractors produce `instructions` as a single string. The `steps` field is a forward-looking addition for future structured step support.
**Affected extractors:** All
**Fix needed:** None immediately; future extractors can populate `steps` when structured step data is available.

### Gap 3: No `tags` Field Currently Produced
**Severity:** Low
**Details:** Extractors produce `keywords` (from JSON-LD or AI), not `tags`. The serialization in `extract_recipe_task.py` stores `keywords` in the dict but the schema defines `tags`.
**Affected extractors:** All
**Fix needed:** Map `keywords` to `tags` during serialization, or add `tags` as an alias.

### Gap 4: Extra Fields Not in Schema
**Severity:** None (informational)
**Details:** Extractors produce additional fields not in the schema: `total_time_minutes`, `author`, `cuisine`, `category`, `keywords`, `raw_data`, `extractor_used`, `text` (on ingredients). These pass validation since the schema allows additional properties. They are consumed downstream by `create_recipe_task.py` and the review UI.

### Gap 5: Ingredient `text` Field Used as Primary Identifier
**Severity:** Low
**Details:** `ExtractedIngredient.text` is the primary required field on the dataclass (original ingredient line like "2 cups flour"), while the schema uses `name` (parsed ingredient name like "flour"). The `text` field flows through as an extra field and is used by the matching pipeline. The two serve different purposes: `text` = display/matching, `name` = canonical ingredient name.
**Fix needed:** Ensure `name` is always populated, potentially falling back to `text` value.

## Testing

All validation paths tested manually:
- Minimal valid recipe (name only)
- Missing required field detection
- Wrong type detection (root and nested)
- Full recipe with all fields
- Ingredient missing required `name`
- Extra fields pass through
- Nullable fields accept `None`
- Array item type validation (e.g. tags must be strings)
- String quantities allowed (e.g. "1/2")
