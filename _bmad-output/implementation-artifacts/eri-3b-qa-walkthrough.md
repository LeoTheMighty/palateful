# eri-3b QA walkthrough — mixed-structure subset filter hardening

Backend-only; no Flutter UI impact. Purely test-coverage-driven story.

## Pre-reqs
- Python 3.13, Poetry, NX.

## Smoke

1. **All integration tests pass.**
   ```bash
   cd libraries/utils && poetry run pytest test/test_extract_recipe_from_html.py -v
   ```
   Expected: 11 passed, including:
   - `test_mixed_structure_only_text_only_strings_are_sent_to_openai`
   - `test_mixed_structure_preserves_structured_rows_and_splices_back_in_order`

2. **Full suite clean.**
   ```bash
   npx nx run utils:test
   npx nx run utils:lint
   ```

## Assertion check

3. **Confirm the subset-only invariant.** The key AC is "structured
   rows' `text` must NEVER land in the OpenAI prompt". The stress
   test inspects the prompt directly — if a future refactor
   accidentally starts sending all rows, this test fails immediately.

## Rollback behavior

4. `EXTRACTOR_JSON_LD_INGREDIENT_PARSE=false` off → parse pass doesn't
   fire → all rows retain their pre-parse state (structured stays
   structured, text-only stays text-only). Confirmed by
   `test_parse_pass_flag_off_does_not_fire`.

## What's deferred
- **Real HowToSupply HTML fixture** — `JsonLdExtractor` doesn't parse
  HowToSupply objects today. If we extend the extractor in a future
  epic, add an HTML fixture that exercises the real shape. The
  current stress test covers the code path via injection.
