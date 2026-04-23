# Story eri-3b — Mixed-structure subset filter + splice in order

**Status:** done
**Epic:** epic-extractor-richer-ingredients
**Branch:** main

## Goal

Harden the subset-filter + splice-in-order path added in eri-3a with
explicit stress tests: when a recipe's ingredients contain a mix of
structured (quantity/unit/name populated) and text-only rows, the
parse pass must receive ONLY the text-only strings and the splice
must land at the original indices.

## Acceptance Criteria — status

| AC | Description | Status |
|----|-------------|--------|
| AC1 | Subset filter sends only text-only strings to `parse_ingredient_strings` | ✅ Done — `test_mixed_structure_only_text_only_strings_are_sent_to_openai` asserts the OpenAI prompt contains text-only strings and NOT structured-row text |
| AC2 | Structured ingredients pass through untouched | ✅ Done — covered by `test_mixed_structure_preserves_structured_rows_and_splices_back_in_order` (from eri-3a) |
| AC3 | Splice back at original indices preserves order | ✅ Done — both tests assert `ingredients[i]` identity at structured indices, filled fields at text-only indices |
| AC4 | Stress case — 3 structured / 2 text-only shuffled (indices 0,2,3 structured; 1,4 text-only) | ✅ Done |

## File List

### Modified
- `libraries/utils/test/test_extract_recipe_from_html.py`
  - Added `test_mixed_structure_only_text_only_strings_are_sent_to_openai`
    which asserts the exact OpenAI prompt payload only contains the
    text-only strings, not the structured-row markers.

### Not modified
- `libraries/utils/utils/services/recipe_extractors/__init__.py` —
  the subset filter (`_text_only_indices` + `_apply_parse_pass`)
  already ships in eri-3a. No code change needed for 3b; the story is
  purely test-coverage + stress hardening.

## Implementation notes

- **Current JsonLdExtractor only emits text-only ingredients.** The
  Schema.org `recipeIngredient` spec is a plain-string list, so
  structured rows can't arrive "for free" from a real site. The
  mixed-structure test simulates the future case (where we might
  extend the extractor to parse `HowToSupply` objects, or where a
  different pre-extractor fills in some rows) by hand-mutating the
  recipe between extract and parse-pass.
- **Why this is still worth testing today:** the code path is live.
  If a future PR extends the extractor or adds a pre-pass, the
  structured rows must still survive unchanged; this test locks that
  contract.
- **Prompt inspection.** The stress test inspects the raw OpenAI
  prompt string (via `MagicMock.call_args`) to assert that structured
  rows' `text` values never land in the prompt. This is the cleanest
  way to guarantee "only the subset was sent".

## Verification

- `npx nx run utils:test` — 511 passed (eri-3a 510 + 1 new eri-3b test)
- `npx nx run utils:lint` — clean
