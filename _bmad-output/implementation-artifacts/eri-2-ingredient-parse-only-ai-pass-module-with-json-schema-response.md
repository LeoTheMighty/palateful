# Story eri-2 — Ingredient parse-only AI pass module (`ingredient_parse.py`)

**Status:** done
**Epic:** epic-extractor-richer-ingredients
**Branch:** main

## Goal

Add a focused gpt-4o-mini call that takes plain-text ingredient
strings (the kind JSON-LD's `recipeIngredient` field emits) and returns
structured `ExtractedIngredient` rows. Gate the response shape with a
strict OpenAI `json_schema` response format so the whole class of
"wrapped-dict" / "dict-instead-of-list" failures is eliminated.
Degrade gracefully on every OpenAI failure class — the downstream
import path must never degrade below today's behavior.

## Acceptance Criteria — status

| AC | Description | Status |
|----|-------------|--------|
| AC1 | `parse_ingredient_strings(strings, openai_client, *, batch_size=25, max_total=200, timeout_seconds=10.0) -> list[ExtractedIngredient]` | ✅ Done |
| AC2 | gpt-4o-mini, temperature 0, strict `json_schema` response format | ✅ Done — `_PARSE_SCHEMA` pins required quantity/unit/name/notes |
| AC3 | Batches of 25 (fixed, not 50-then-remainder); cap at 200 total | ✅ Done — constants `_DEFAULT_BATCH_SIZE = 25`, `_DEFAULT_MAX_TOTAL = 200` pinned by test |
| AC4 | Overflow beyond `max_total` returns text-only + one `IngredientParsePathological` audit row | ✅ Done |
| AC5 | Graceful fallback on: rate limit, timeout, 5xx, schema violation, empty response, malformed JSON, wrong-count response — each emits `IngredientParseFailure` audit row with `error_class` | ✅ Done |
| AC6 | Partial success across batches preserved — earlier successful batches kept when a later batch fails | ✅ Done |
| AC7 | Per-call token count logged (info level) for cost true-up in the first week | ✅ Done |
| AC8 | Prompt splices in `unit_rule()` from `unit_prompt.py` — single source of truth for the soften/canonical/freeform decision | ✅ Done |
| AC9 | Unit tests with MagicMock OpenAI: happy path, batching, cap, each failure class, partial-success, per-call-kwarg pinning | ✅ Done — 21 new tests |
| AC10 | `text` field of returned `ExtractedIngredient` preserves the original raw input (matches `JsonLdExtractor`'s invariant so UI + downstream normalize behavior are unchanged) | ✅ Done |

## File List

### New
- `libraries/utils/utils/logging/ingredient_parse_logging.py`
  - `log_ingredient_parse_failure(...)` — `IngredientParseFailure` audit row
  - `log_ingredient_parse_pathological(...)` — `IngredientParsePathological` audit row
  - `log_ingredient_field_coverage(...)` — `IngredientFieldCoverage` audit row (eri-3a consumer, placed here for module cohesion)
  - Uses its own `Database()` session so caller's txn can rollback without losing audit rows; never raises.
- `libraries/utils/utils/services/recipe_extractors/ingredient_parse.py`
  - `parse_ingredient_strings(...)` — public entry point
  - `_parse_one_batch(...)` — per-batch OpenAI call + fallback
  - `_build_prompt(...)` — ingredient-only prompt that embeds `unit_rule()`
  - `_to_text_only(...)` — fallback helper
  - `_PARSE_SCHEMA` — strict json-schema pinning array-of-objects shape
- `libraries/utils/test/test_ingredient_parse.py` — 21 unit tests

## Schema contract

```
{
  "ingredients": [
    {"quantity": <number|null>, "unit": <string|null>,
     "name": <string>, "notes": <string|null>}
  ]
}
```

Top-level object must contain exactly `ingredients`. Each item must
contain exactly `quantity`, `unit`, `name`, `notes`. `additionalProperties`
is false. Any deviation → schema violation audit row + text-only
fallback.

## Failure → audit mapping

| Failure | `error_class` emitted | Fallback |
|--|--|--|
| OpenAI rate limit / 429 | `RateLimitError` (or raised class name) | Whole batch as text-only |
| OpenAI timeout / read timeout | `APITimeoutError` / `TimeoutError` | Whole batch as text-only |
| OpenAI 5xx / network | `APIError` / raised class name | Whole batch as text-only |
| Empty `content` string | `EmptyResponse` | Whole batch as text-only |
| Non-JSON body | `JSONDecodeError` | Whole batch as text-only |
| Wrong shape / wrong count | `SchemaViolation` (+ `extra.got_len`) | Whole batch as text-only |
| Per-row non-dict item | (no audit — one-off) | Just that row as text-only |
| > `max_total` strings | N/A (pathological audit, not failure) | Overflow as text-only |

## Implementation notes

- **Sync, not async.** The epic text reads `async def` but every
  existing extractor is sync; making this one async would force
  `extract_recipe_from_html` (the eri-3a caller) async and cascade
  through every task that imports it. Sync is the pragmatic choice.
- **`text` preservation.** When the LLM succeeds we still set `text`
  to the stripped original input string. This matches what
  `JsonLdExtractor` emits today (`ExtractedIngredient(text=ing_text.strip())`)
  and keeps the Flutter review-screen renderer stable. Quantity/unit
  are rendered as separate chips, so the duplication is harmless.
- **No confidence re-scoring.** Per epic design principle 5: parse-pass
  output doesn't inflate or penalize the recipe's confidence score.
  That's `extract_recipe_from_html`'s job (nothing to do).
- **`utils.logging.ingredient_parse_logging`** grew
  `log_ingredient_field_coverage()` preemptively even though eri-3a
  is the consumer — the 3 helpers share metadata caps and the
  short-lived DB-session pattern, and centralizing them keeps the
  pattern auditable from one file.

## Verification

- `npx nx run utils:test` — 500 passed (was 480; +21 new + 1 paired test)
- `npx nx run utils:lint` — clean
