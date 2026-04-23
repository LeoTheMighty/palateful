# Story eri-3a — `extract_recipe_from_html` parse-pass invocation + coverage audit

**Status:** done
**Epic:** epic-extractor-richer-ingredients
**Branch:** main

## Goal

Wire `parse_ingredient_strings` (eri-2) into `RecipeExtractorRegistry.extract()`
so that when `JsonLdExtractor` succeeds, the text-only subset of its
ingredients goes through the parse pass and the results splice back
in-order. Emit one `IngredientFieldCoverage` audit row per successful
extraction whether the pass fired or not so production field-completeness
trend is visible in `error_logs`.

## Acceptance Criteria — status

| AC | Description | Status |
|----|-------------|--------|
| AC1 | `_json_ld_parse_enabled()` reads `EXTRACTOR_JSON_LD_INGREDIENT_PARSE` at call time, default-on | ✅ Done |
| AC2 | After JSON-LD extraction succeeds, parse pass runs on text-only subset (qty/unit/name all None AND text non-empty) | ✅ Done — `_text_only_indices(...)` + `_apply_parse_pass(...)` |
| AC3 | Parse-pass results splice back at original indices — input order preserved | ✅ Done |
| AC4 | Structured ingredients from JSON-LD pass through untouched (mixed-structure support, eri-3b confirms with test) | ✅ Done |
| AC5 | All-structured JSON-LD skips the parse pass (no cost) | ✅ Done |
| AC6 | Flag off skips the parse pass | ✅ Done |
| AC7 | `IngredientFieldCoverage` audit row written per successful extraction with `{total, qty_present, unit_present, name_present, notes_present, source, url_host}` | ✅ Done — `_emit_coverage_audit(...)` |
| AC8 | `source` is one of `"json_ld"`, `"json_ld_parse_pass"`, `"ai_extractor"` | ✅ Done |
| AC9 | AI-fallback path (no JSON-LD) still emits coverage audit | ✅ Done |
| AC10 | Integration tests against clove, gram, range, mixed-structure, all-structured, flag-off, AI-fallback, null-url | ✅ Done — 10 new tests |

## File List

### New
- `libraries/utils/test/test_extract_recipe_from_html.py` — 10 integration tests

### Modified
- `libraries/utils/utils/services/recipe_extractors/__init__.py`
  - Added `_json_ld_parse_enabled()` — flag reader
  - Added `_text_only_indices(recipe)` — subset finder
  - Added `_apply_parse_pass(recipe, *, openai_client, url)` — runs parse pass + splices results back
  - Added `_count_presence(recipe)` — per-field presence counts
  - Added `_emit_coverage_audit(recipe, *, source, url)` — `IngredientFieldCoverage` writer
  - Modified `RecipeExtractorRegistry.extract()` to call both helpers after a successful extraction (JSON-LD path: parse pass + audit; AI fallback path: audit only)

## Pipeline shape (post eri-3a)

```
HTML → RecipeExtractorRegistry.extract()
       │
       ├─ JsonLdExtractor.extract() → Recipe with text-only ingredients
       │    └─ if EXTRACTOR_JSON_LD_INGREDIENT_PARSE and text-only subset:
       │         parse_ingredient_strings(subset) → splice back in order
       │    └─ _emit_coverage_audit(source="json_ld" | "json_ld_parse_pass")
       │
       └─ AIExtractor.extract()  (fallback, no JSON-LD)
            └─ _emit_coverage_audit(source="ai_extractor")
```

## Implementation notes

- **OpenAI client source.** The parse pass uses
  `self._ai_extractor.client` — the same lazily-constructed OpenAI
  client the AI-fallback extractor would have used. One client per
  registry, shared across both paths. `extract_recipe_from_html`'s
  `openai_client` param still flows through to that shared client on
  first construction via `get_default_registry(openai_client)`.
- **Audit emission placement.** The coverage audit fires in the
  registry, not in the extractor. That keeps extractors stateless and
  centralizes the "what source delivered these fields" decision in
  the one place that orchestrates the fallback chain.
- **`url_host`.** Extracted via `urlparse(url).hostname` so the host
  is normalized (strips port, lowercased by the parser). `None` is
  passed through cleanly when `url is None` (e.g. `extract_recipe_from_html`
  called with raw HTML only).
- **No confidence re-scoring** (per epic design principle 5). The
  parse pass replaces `ExtractedIngredient` objects but
  `recipe.confidence_score` / `recipe.confidence_source` stay at
  `JsonLdExtractor`'s values. Ingredients are review-editable anyway.
- **Empty-ingredient tolerance.** If `recipe.ingredients` is empty,
  no audit row is emitted — `_count_presence` would just report all
  zeros, which is not a useful signal.

## Verification

- `npx nx run utils:test` — 510 passed (+10 eri-3a tests)
- `npx nx run utils:lint` — clean
- `npx nx run api:test` — 2257 passed, coverage 100%
- `npx nx run api:lint` — clean
