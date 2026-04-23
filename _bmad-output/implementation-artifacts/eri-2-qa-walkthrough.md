# eri-2 QA walkthrough — ingredient_parse.py

Backend-only; no Flutter UI impact. The module is dormant until
`extract_recipe_from_html` wires it up in eri-3a — this walkthrough
just checks the module loads, tests pass, and the shape contract is
sound.

## Pre-reqs
- Python 3.13, Poetry, NX.

## Smoke

1. **Unit tests pass.**
   ```bash
   npx nx run utils:test
   ```
   Expected: 500 passed, coverage unchanged.

2. **Lint clean.**
   ```bash
   npx nx run utils:lint
   ```

## Module sanity

3. **Public entry point is importable.**
   ```bash
   cd libraries/utils && poetry run python -c "
   from utils.services.recipe_extractors.ingredient_parse import parse_ingredient_strings
   print(parse_ingredient_strings.__doc__[:80])
   "
   ```
   Expected: prints the first line of the docstring.

4. **Empty-input short-circuit works without touching OpenAI.**
   ```bash
   cd libraries/utils && poetry run python -c "
   from unittest.mock import MagicMock
   from utils.services.recipe_extractors.ingredient_parse import parse_ingredient_strings
   c = MagicMock()
   r = parse_ingredient_strings([], c)
   assert r == [], r
   assert not c.chat.completions.create.called
   print('OK')
   "
   ```

5. **Overflow fall-through is text-only.**
   ```bash
   cd libraries/utils && poetry run python -c "
   from unittest.mock import MagicMock, patch
   from utils.services.recipe_extractors.ingredient_parse import parse_ingredient_strings
   c = MagicMock()
   c.chat.completions.create.side_effect = RuntimeError('should not be called')
   with patch('utils.services.recipe_extractors.ingredient_parse.log_ingredient_parse_pathological'):
       with patch('utils.services.recipe_extractors.ingredient_parse.log_ingredient_parse_failure'):
           r = parse_ingredient_strings(['a','b','c'], c, batch_size=1, max_total=0)
   assert len(r) == 3
   assert all(x.quantity is None and x.name is None for x in r)
   print('OK')
   "
   ```

## Audit-row payload

6. **`IngredientParseFailure` helper is callable (dry-run: DB import will fail silently in this shell without DATABASE_URL, but the helper must not raise).**
   ```bash
   cd libraries/utils && poetry run python -c "
   from utils.logging.ingredient_parse_logging import log_ingredient_parse_failure
   log_ingredient_parse_failure(error_class='Test', batch_size=3, url_sample='https://example.com')
   print('OK — did not raise')
   "
   ```

## What's deferred

- **Wiring into extract_recipe_from_html** — eri-3a.
- **Production token-cost observation** — first week of prod data will inform whether `_DEFAULT_BATCH_SIZE` stays at 25.
- **`IngredientFieldCoverage` audit emission** — eri-3a (the helper is already in place).
