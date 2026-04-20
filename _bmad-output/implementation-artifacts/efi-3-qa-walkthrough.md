# efi-3 — QA walkthrough

Backend persistence wiring. No UI, no direct API consumer yet (efi-4
hoists onto import-item responses; efi-5+ wire the Flutter badge).
Verification runs in two tracks: (1) the new unit + integration tests,
(2) a live spot-check that an extractor emitting `inferred_fields`
flows through to the recipes table.

## Local checks

```bash
poetry run pytest libraries/utils/test/test_extract_recipe_task_inference.py libraries/utils/test/test_create_recipe_task_inferred_fields.py --no-cov
DATABASE_URL=sqlite:///test.db AUTH0_DOMAIN=test.auth0.com AUTH0_AUDIENCE=https://api.palateful.test poetry run pytest services/api/tests/test_recipe.py --no-cov
npx nx run api:lint       # src/ only — should pass once parallel WIP in list_activities.py + str-ing-4 drop-migration commits and cleans up.
npx nx run utils:lint     # utils/ only — two pre-existing F822 errors from str-ing-4 WIP in db/models.py; my files green.
```

Expected: 12 utils tests green, 2049 api tests green, both lints clean
against my files only.

## Migration sanity

```bash
# Against the migrator's own test DB once it exists:
npx nx run migrator:check-models
```

If clean, the Alembic chain `abi2bsoftarch1 → efi3infrfields1` materializes
`recipes.inferred_fields JSONB NOT NULL DEFAULT '[]'` with historical rows
defaulted. Down-migration drops the column cleanly.

## End-to-end flow spot-check

```bash
# With EXTRACTOR_INFER_MISSING_FIELDS=true (default), mock an extraction
# that emits `inferred_fields` and watch the full pipeline:
EXTRACTOR_INFER_MISSING_FIELDS=true poetry run python - <<'PY'
from utils.services.recipe_extractors.base import ExtractedRecipe
from utils.services.recipe_extractors.inference_guardrails import apply_guardrails
from utils.services.recipe_extractors.confidence_heuristic import apply_inference_penalty

recipe = ExtractedRecipe(
    name="Brownies",
    cook_time_minutes=9999,      # out of range → clamps to 720
    prep_time_minutes=15,
    servings=16,
    cuisine="A" * 200,           # over cap → truncated to 40
    primary_vibe="bogus",        # invalid → dropped
    inferred_fields=[
        "cook_time_minutes",
        "prep_time_minutes",
        "servings",
        "cuisine",
        "primary_vibe",
    ],
)
recipe.confidence_score = 0.80
apply_guardrails(recipe, import_item_id=None)
recipe.confidence_score = apply_inference_penalty(
    recipe.confidence_score, len(recipe.inferred_fields)
)
print("inferred_fields =", recipe.inferred_fields)
print("cook_time =", recipe.cook_time_minutes)
print("cuisine =", recipe.cuisine)
print("primary_vibe =", recipe.primary_vibe)
print("confidence_score =", recipe.confidence_score)
PY
```

Expected: `inferred_fields` = `[cook_time_minutes, prep_time_minutes,
servings, cuisine]` (vibe dropped); `cook_time = 720`; `cuisine` = 40-char
truncation; `primary_vibe = None`; `confidence_score ≈ 0.60` (0.80 − 4 ×
0.05).

## Shrink-only round-trip via API

Requires a running dev server + a real recipe with pre-existing inferred
fields. Curl-style:

```bash
# Read current state.
curl -s ":API/v1/recipes/$RECIPE_ID" -H "Authorization: Bearer $TOKEN" | jq .inferred_fields

# Valid shrink — drops servings from the list, keeps cook_time_minutes.
curl -sX PUT ":API/v1/recipes/$RECIPE_ID" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"inferred_fields": ["cook_time_minutes"]}' | jq .

# Invalid expansion — should 400 with data.allowed == ["cook_time_minutes"].
curl -sX PUT ":API/v1/recipes/$RECIPE_ID" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"inferred_fields": ["cook_time_minutes", "servings"]}' | jq .
```
