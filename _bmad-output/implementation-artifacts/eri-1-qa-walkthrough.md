# eri-1 QA walkthrough — softened unit rule + flag precedence

Backend-only story. No Flutter UI changes. The checks below verify
prompt content, flag precedence, and the rollback path.

## Pre-reqs
- Python 3.13, Poetry, NX.

## Smoke

1. **Unit tests pass.**
   ```bash
   npx nx run utils:test
   ```
   Expect 480 passed (includes the new `test_unit_prompt_precedence.py` 20+ tests).

2. **Lint clean.**
   ```bash
   npx nx run utils:lint
   npx nx run api:lint
   ```

## Prompt-content spot-check

3. **Default rule (both flags unset) is SOFTENED.**
   ```bash
   cd libraries/utils && poetry run python -c "
   from utils.services.recipe_extractors.unit_prompt import unit_rule
   print(unit_rule(freeform_fallback='LEGACY'))
   "
   ```
   Expected substrings in output:
   - `"prefer one of these tokens"`
   - `` `clove` ``, `` `stalk` ``, `` `bunch` ``, `` `drop` ``
   - `"convertible"`
   - `"3 large eggs"` (count rule)
   - `"salt to taste"` (uncountable rule)
   - Absent: `"use EXACTLY one of these tokens"`, `"LEGACY"`

4. **Canonical path is reachable.**
   ```bash
   cd libraries/utils && EXTRACTOR_SOFTEN_UNIT_RULE=false poetry run python -c "
   from utils.services.recipe_extractors.unit_prompt import unit_rule
   print(unit_rule(freeform_fallback='LEGACY'))
   "
   ```
   Output should contain `"use EXACTLY one of these tokens"` and NOT `"prefer"`.

5. **Freeform rollback path is reachable.**
   ```bash
   cd libraries/utils && EXTRACTOR_SOFTEN_UNIT_RULE=false EXTRACTOR_EMIT_CANONICAL_UNITS=false poetry run python -c "
   from utils.services.recipe_extractors.unit_prompt import unit_rule
   print(unit_rule(freeform_fallback='LEGACY'))
   "
   ```
   Output must be exactly `LEGACY`.

## Per-extractor prompt sanity

6. **All three extractors embed the softened rule by default.**
   ```bash
   cd libraries/utils && poetry run python -c "
   from utils.services.recipe_extractors.ai_extractor import _extraction_prompt
   from utils.services.recipe_extractors.text_extractor import _text_extraction_prompt
   from utils.services.recipe_extractors.vision_extractor import _vision_system_prompt
   for name, fn in [('ai', _extraction_prompt), ('text', _text_extraction_prompt), ('vision', _vision_system_prompt)]:
       p = fn()
       assert 'prefer one of these tokens' in p, f'{name} missing softened rule'
       assert '1 clove garlic, minced' in p, f'{name} missing clove example'
       assert '2 stalks celery, chopped' in p, f'{name} missing stalk example'
       assert '300 gram of vinegar' in p, f'{name} missing gram example'
       assert '1-2 cups water' in p, f'{name} missing range example'
       assert 'a pinchful of salt' in p, f'{name} missing substring example'
       assert 'Do NOT hallucinate notes' in p, f'{name} missing anti-hallucination'
       print(f'{name}: OK')
   "
   ```

## Flutter guard

7. **No client-side enum validation rejects non-canonical units on save.**
   ```bash
   grep -rn "assert.*unit\b\|throw.*unit" app/lib/ | grep -v ".g.dart"
   ```
   Expected: no hits.

## Rollback drill

8. Flip both flags off in ECS task def:
   - `EXTRACTOR_SOFTEN_UNIT_RULE=false`
   - `EXTRACTOR_EMIT_CANONICAL_UNITS=false`

   Import any recipe URL → behavior matches pre-riip-3 (freeform unit words in prompt).
   The runbook in eri-6 owns this drill operationally.
