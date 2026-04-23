# eri-3a QA walkthrough — JSON-LD parse-pass wiring + coverage audit

Backend-only; no Flutter UI impact. This is the first story where the
pipeline actually calls the parse pass in anger, so the checks are
heavier than eri-1/2.

## Pre-reqs
- Python 3.13, Poetry, NX.

## Smoke

1. **Unit + integration tests pass.**
   ```bash
   npx nx run utils:test
   npx nx run api:test
   ```
   Expected: utils 510 passed, api 2257 passed (100% cov).

2. **Lint clean.**
   ```bash
   npx nx run utils:lint
   npx nx run api:lint
   ```

## Flag sanity

3. **Default is ON.**
   ```bash
   cd libraries/utils && poetry run python -c "
   from utils.services.recipe_extractors import _json_ld_parse_enabled
   print(_json_ld_parse_enabled())
   "
   ```
   Expected: `True`.

4. **`false` disables.**
   ```bash
   cd libraries/utils && EXTRACTOR_JSON_LD_INGREDIENT_PARSE=false poetry run python -c "
   from utils.services.recipe_extractors import _json_ld_parse_enabled
   print(_json_ld_parse_enabled())
   "
   ```
   Expected: `False`.

## Integration walkthrough (mock OpenAI)

5. **Clove regression end-to-end.**
   ```bash
   cd libraries/utils && poetry run python <<'PY'
from json import dumps
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from utils.services.recipe_extractors import extract_recipe_from_html

html = '''<html><head><script type="application/ld+json">{
"@context":"https://schema.org","@type":"Recipe",
"name":"Clove Test",
"recipeIngredient":["1 clove garlic, minced","2 tbsp olive oil"],
"recipeInstructions":"Stir."
}</script></head><body><h1>Clove Test</h1></body></html>'''

client = MagicMock()
client.chat.completions.create.return_value = SimpleNamespace(
    choices=[SimpleNamespace(message=SimpleNamespace(content=dumps({
        "ingredients":[
          {"quantity":1,"unit":"clove","name":"garlic","notes":"minced"},
          {"quantity":2,"unit":"tbsp","name":"olive oil","notes":None},
        ]})))],
    usage=SimpleNamespace(total_tokens=80),
)

# Silence audit writers so we don't need a live DB.
with patch('utils.services.recipe_extractors.log_ingredient_field_coverage'):
    with patch('utils.services.recipe_extractors.ingredient_parse.log_ingredient_parse_failure'):
        with patch('utils.services.recipe_extractors.ingredient_parse.log_ingredient_parse_pathological'):
            import utils.services.recipe_extractors as m
            m._default_registry = None
            r = extract_recipe_from_html(html, url="https://example.com/clove", openai_client=client)

assert r.success
ings = r.recipe.ingredients
assert ings[0].quantity == 1 and ings[0].unit == "clove" and ings[0].name == "garlic"
assert ings[1].quantity == 2 and ings[1].unit == "tbsp"
print("OK — clove parse pass fired end-to-end")
PY
   ```

## Audit-emission sanity

6. **Verify the coverage helper is called with the right shape.** The
   integration test `test_clove_regression_parses_from_json_ld` already
   asserts this; just re-run it in isolation:
   ```bash
   cd libraries/utils && poetry run pytest test/test_extract_recipe_from_html.py::test_clove_regression_parses_from_json_ld -v
   ```

## Rollback drill

7. Flip `EXTRACTOR_JSON_LD_INGREDIENT_PARSE=false` in ECS task def.
   Re-import any recipe URL → Review Import shows text-only ingredients
   (same as pre-ERI). No parse-pass cost. Coverage audit still fires
   with `source="json_ld"`.

## What's deferred
- **Mixed-structure integration test with HTML fixture** — eri-3b adds
  a dedicated test that sources the structured rows directly from
  JSON-LD `HowToSupply` objects (rather than hand-mutating the recipe
  post-extraction). Current mixed-structure test covers the code path
  but not the HTML shape.
- **Per-call token cost dashboard** — eri-6 (rollout runbook).
