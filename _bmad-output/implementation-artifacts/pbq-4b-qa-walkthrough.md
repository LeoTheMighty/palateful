# QA walkthrough — pbq-4b unified_search semantic tier selectinload

## What shipped

Both `_search_my_recipes_semantic` and
`_search_public_recipes_semantic` attach a
`selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient)`
chain to their `select()` statement. The post-result Python loop
(`recipe.ingredients[:5]` + `ri.ingredient.canonical_name`) now reads
against the eager-loaded rows instead of firing 2×limit lazy-load
queries per call.

## Before/after numbers

### Query shape

| Tier | Pre-pbq-4b | Post-pbq-4b |
| --- | --- | --- |
| `_search_my_recipes_semantic` (limit=20) | 1 + 20 + 20×N_ingr | **3** (main + ingredients IN + ingredient IN) |
| `_search_public_recipes_semantic` (limit=20) | 1 + 20 + 20×N_ingr | **3** |

### Latency (single-operator prod)

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --window 24h --format csv --top 40 \
    | grep "search\|embeddings"
```

Method: pin baseline → redeploy → 30-min follow-up. Single-operator
prod rarely falls through to the semantic tier (the exact + fuzzy
tiers usually fill the `limit`), so the measurable p95 win is
modest. The value of this fix compounds as recipe volume grows.

### EXPLAIN (post-deploy)

Captured against prod when the semantic tier actually fires (pass a
query that doesn't match any recipe name / description / ingredient
exact or fuzzy). Expected plan shape:

- Main semantic query: pgvector index scan on
  `recipes.embedding` with cosine-distance order + limit.
- `ingredients` selectinload: hash/bitmap scan on
  `recipe_ingredients.recipe_id` (index-backed FK).
- `ingredient` selectinload: index scan on `ingredients.id` (PK).

Drop into the QA walkthrough post-deploy; no plan regression expected
because the two eager-load leaves are additive (new separate queries,
not a join on the main statement).

## How to verify

### 1. Local tests green

```bash
npx nx run api:test -- tests/test_search.py --no-cov
# test_semantic_tier_eager_loads_recipe_ingredients passes
```

### 2. Test locks in the fix

- Module-level `selectinload` spy asserts the outer call on
  `Recipe.ingredients` fires 2+ times (once per tier).
- Source inspection via `inspect.getsource` asserts the nested
  `.selectinload(RecipeIngredient.ingredient)` literal is present on
  each semantic handler — a refactor that dropped the chain would
  trip the assertion.

### 3. Manual verification

```bash
curl -H "Authorization: Bearer <token>" \
     "https://api.palateful.app/v1/search?q=aromatic+star+anise+pho"
```

Response shape byte-identical. If the semantic tier fires, `my_recipes`
and `public_recipes` entries carry `ingredients: ["..."]` arrays
populated from the eager-loaded join.

## Checklist

- [x] `.options(selectinload(Recipe.ingredients)
      .selectinload(RecipeIngredient.ingredient))` on both semantic
      tiers.
- [x] Test verifies outer selectinload wiring + structural source
      presence of the nested chain.
- [x] Exact / fuzzy tiers untouched.
- [x] No response-shape change.
- [x] EXPLAIN capture recipe documented for post-deploy.

## Rollback

```bash
git revert <pbq-4b-commit>
```

Drops the two `.options()` blocks; restores the lazy-load fallback.
