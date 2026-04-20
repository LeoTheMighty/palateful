# efi-2 — QA walkthrough

Prompt + parse story. No DB, no UI. Verification: run the new test
module, spot-read the flag-on vs flag-off prompts for each of the
three LLM extractors, and exercise a parse path with a mock payload.

## Local checks

```bash
cd libraries/utils && poetry run pytest test/test_extractor_inferred_fields.py
npx nx run utils:lint
cd libraries/utils && poetry run pytest test/   # 367 total, no regressions
```

Expected: 28 new tests green, 367 total utils tests green, lint clean.

## Flag-on prompt sanity (ai, text, vision)

```bash
cd libraries/utils && EXTRACTOR_INFER_MISSING_FIELDS=true poetry run python -c "
from utils.services.recipe_extractors.ai_extractor import _extraction_prompt
from utils.services.recipe_extractors.text_extractor import _text_extraction_prompt
from utils.services.recipe_extractors.vision_extractor import _vision_system_prompt
for name, fn in [('ai', _extraction_prompt), ('text', _text_extraction_prompt), ('vision', _vision_system_prompt)]:
    p = fn()
    print(name, 'has inferred_fields =', 'inferred_fields' in p)
    print(name, 'has NEVER clause =', 'NEVER infer name' in p)
    print(name, 'has cook_time example =', 'cook_time_minutes: 27' in p)
    print()
"
```

Expected: all three print `True` for each check.

## Flag-off prompt sanity (the one AC7 case reviewers flagged as a potential leak)

```bash
EXTRACTOR_INFER_MISSING_FIELDS=false poetry run python -c "
from utils.services.recipe_extractors.ai_extractor import _extraction_prompt
from utils.services.recipe_extractors.text_extractor import _text_extraction_prompt
from utils.services.recipe_extractors.vision_extractor import _vision_system_prompt
for name, fn in [('ai', _extraction_prompt), ('text', _text_extraction_prompt), ('vision', _vision_system_prompt)]:
    p = fn()
    print(name, 'leaks inferred_fields =', 'inferred_fields' in p)
    print(name, 'leaks NEVER clause =', 'NEVER infer name' in p)
    print(name, 'leaks Field-level =', 'Field-level inference' in p)
    print()
"
```

Expected: every line prints `False` — the flag-off prompt must not
mention `inferred_fields` anywhere, otherwise the model would still be
primed to emit the key.

## Parse path sanity

```bash
cd libraries/utils && poetry run python -c "
from utils.services.recipe_extractors.ai_extractor import AIExtractor
extr = AIExtractor()
recipe = extr._parse_ai_response({
    'name': 'Test',
    'ingredients': [],
    'inferred_fields': ['cook_time_minutes', 'servings', 'bogus', 'name', 'cook_time_minutes'],
})
print('parsed =', recipe.inferred_fields)
"
```

Expected: `parsed = ['cook_time_minutes', 'servings']` — bogus + name
filtered out, duplicate deduped, order preserved.

## JSON-LD untouched check

```bash
cd libraries/utils && poetry run python -c "
from utils.services.recipe_extractors.json_ld import JsonLdExtractor
r = JsonLdExtractor()._parse_recipe_data({
    'name': 'Test', 'recipeIngredient': ['1 cup flour'], 'recipeInstructions': 'Bake.'
})
print('inferred_fields =', r.inferred_fields)
"
```

Expected: `inferred_fields = []` — JSON-LD is Schema.org-authoritative
and never infers regardless of flag state.

## Regression checks (zero-inferred happy path)

- Existing `test_extractor_confidence.py` — all 44 tests pass without modification.
- Existing `test_ai_extractor_timers.py` — all 10 tests pass without modification.
- Existing `test_recipe_extractors_array_contract.py` — all tests pass without modification.
- `ExtractedRecipe()` with no `inferred_fields` arg → field defaults to `[]`; no existing call-site needed updating.

## Not verified in this story

- End-to-end extractor → task → DB persistence — lands in efi-3.
- Real LLM runs with / without the flag — manual smoke only; no eval
  metric exists yet (lands in efi-8).
- Flutter model decoding of `inferred_fields` — efi-5.
