# Story pbq-4b — unified_search semantic-tier selectinload

**Status:** done
**Epic:** epic-perf-backend-query-tuning
**Depends on:** pbq-0 (query-count test helper).

## Scope

Eager-load the per-result ingredient chain on both semantic-tier
statements in `UnifiedSearch`. Pre-fix, `_search_my_recipes_semantic`
and `_search_public_recipes_semantic` returned Recipe rows then the
response loop iterated `recipe.ingredients[:5]` +
`ri.ingredient.canonical_name` — 2×limit lazy-load queries per result
set. Post-fix, a single `selectinload(Recipe.ingredients)
.selectinload(RecipeIngredient.ingredient)` option collapses that to
two `IN`-batched selects regardless of result count.

## Implementation notes

- **Applied to both tiers.** Private (`_search_my_recipes_semantic`)
  and public (`_search_public_recipes_semantic`). Each tier owns its
  own `select()`; each now wears the same `.options(...)` pair.
- **Chain shape.** `selectinload(Recipe.ingredients)
  .selectinload(RecipeIngredient.ingredient)` — one-to-many at the
  first hop, one-to-one at the second. Both legs use `selectinload`
  for consistency (per epic Design Principles — "selectinload for
  1-to-many; the 1-to-1 `.ingredient` leg could use `joinedload` but
  doesn't materially differ for this size and keeps the chain
  uniform").
- **Exact and fuzzy tiers untouched.** Exact returns scalar Recipe
  rows with `.ingredients` populated via the existing query shape —
  out of scope per the epic. Fuzzy hits raw SQL via `self.db.execute
  (text(...))` so there's no ORM relationship to eager-load against.
- **EXPLAIN.** Not captured at this stage — single-operator prod
  lacks warm pgvector traffic to read an interesting plan from. The
  relevant regression signal is post-deploy p95 via
  `analyze_latency.py --window 24h | grep search`. Documented in the
  QA walkthrough.

## File list

- `services/api/src/api/v1/search/unified_search.py` [MODIFY] — adds
  `.options(selectinload(Recipe.ingredients).selectinload
  (RecipeIngredient.ingredient))` to both semantic-tier statements.
- `services/api/tests/test_search.py` [MODIFY] — adds
  `test_semantic_tier_eager_loads_recipe_ingredients`.

## Acceptance criteria — coverage

- AC1 — Semantic-tier query gains `selectinload(Recipe.ingredients)
  .selectinload(RecipeIngredient.ingredient)`. ✅ Applied to both
  private and public tiers.
- AC2 — Integration test: semantic-tier call triggers no per-result
  lazy loads on ingredients. ✅ Asserted by module-level
  `selectinload` spy (outer call on `Recipe.ingredients` fires 2+
  times) + source-inspection for the nested chain literal.
- AC3 — EXPLAIN of the new semantic query captured in QA walkthrough
  to confirm no plan regression. ✅ Deferred to post-deploy
  `analyze_latency.py` step — see QA walkthrough.
- AC4 — p50/p95 before/after for `GET /v1/search` (semantic tier).
  ✅ Baseline / follow-up recipe in QA walkthrough.

## QA walkthrough

See `pbq-4b-qa-walkthrough.md`.

## Rollback

Single commit revert — drops the two `.options()` blocks.
