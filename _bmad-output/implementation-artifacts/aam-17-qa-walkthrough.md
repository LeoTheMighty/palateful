# aam-17 — Search Domain Async — QA Walkthrough

**Scope:** Convert the `UnifiedSearch` endpoint + its router handler +
the `unified_search` MCP tool from sync to async, and rewrite
`test_search.py` + `test_unified_search_with_meals.py` +
`mcp_server/test_search_tools.py` to the `mock_async_db` pattern.

Explicitly out of scope:
- `api/v1/search/generate_recipe_embedding.py` (sync standalone helpers
  for `generate_recipe_embedding` + `assign_vibes_for_recipe`) — still
  consumed by sync recipe-writes (aam-12b backlog) and the worker.
- `TestGenerateRecipeEmbedding` / `TestAssignVibesForRecipe` test classes
  — exercise the still-sync helpers above; no change.
- `AsyncOpenAI` swap — owned by aam-7 (Phase 2). The sync OpenAI call
  inside `_generate_query_embedding` is wrapped via `run_in_threadpool`
  until that story lands.

## Smoke checklist

All 79 search-domain tests green locally:

```
cd services/api && DATABASE_URL=postgresql://x/y poetry run pytest \
    tests/test_search.py \
    tests/test_unified_search_with_meals.py \
    tests/mcp_server/test_search_tools.py \
    --no-cov --tb=short -q
# → 79 passed
```

Coverage on the converted surfaces: 100% on all three files
(`unified_search.py`, `search_router.py`, `mcp_server/tools/search.py`).

Lint green:

```
npx nx run api:lint
# → All checks passed!
```

## Endpoint-by-endpoint trace

### GET /v1/search (`UnifiedSearch`)

- **Handler (router):** `async def search` ← `get_current_user_async`,
  `get_async_database` ← `await UnifiedSearch.call(...)`
- **Endpoint:** inherits `AsyncEndpoint`, `async def execute`
- **Public method shape** is unchanged (same Params, same Response).
- **DB calls (every method awaiting `db.execute`):**
  - `_get_my_book_ids` — single `await db.execute(select(RecipeBookUser.
    recipe_book_id).where(user_id==..))`, result memoized on
    `self._my_book_ids`.
  - `_search_my_recipes` — `await db.execute(select(Recipe,
    RecipeBook.name).join().options(selectinload(...)).where(...))`.
  - `_search_public_recipes` — same shape, with `owner_subq` join.
  - `_search_my_recipes_fuzzy`, `_search_public_recipes_fuzzy` — `await
    db.execute(text("""..."""), params)` (raw pg_trgm SQL). Wrapped in
    `try/except Exception: return []` so environments without pg_trgm
    degrade silently.
  - `_search_my_recipes_semantic`, `_search_public_recipes_semantic` —
    `await db.execute(select(Recipe).where(embedding_distance<0.7)...)`,
    same `try/except: return []` degrade path for envs without pgvector.
  - `_search_my_meals` — two executes (direct + component-name passes),
    second skipped when direct fills the limit.
  - `_search_users` — 4 sequential executes (search + friendships + sent
    + received requests).
- **Sync boundary:** `_generate_query_embedding` runs the synchronous
  OpenAI client inside `run_in_threadpool(self._sync_generate_query_
  embedding, query)` so the event loop stays free while the HTTPS call
  happens.
- **Test file coverage:** 27 `TestUnifiedSearch` + `TestUnifiedSearchDirect`
  scenarios in `test_search.py`, 18 `TestResolveScope` + `TestSearchMyMeals`
  + `TestUnifiedSearchScopeIntegration` scenarios in
  `test_unified_search_with_meals.py`, and 3 MCP wrapper scenarios in
  `mcp_server/test_search_tools.py`. Plus the still-sync
  `TestGenerateRecipeEmbedding` / `TestAssignVibesForRecipe` helper tests
  (kept as-is).

## Lazy-load audit

Search results include: `recipe.ingredients[:5]` with
`ri.ingredient.canonical_name`, plus `meal.components` with
`comp.recipe.name`, `comp.recipe.archived_at`, `comp.recipe.image_url`,
`comp.recipe.recipe_book.archived_at`.

All three hot chains are eager-loaded:

- `_search_my_recipes` / `_search_public_recipes`: `selectinload(Recipe.
  ingredients).selectinload(RecipeIngredient.ingredient)`.
- `_search_my_recipes_semantic` / `_search_public_recipes_semantic`: same
  chain (pbq-4b).
- `_search_my_meals`: `selectinload(Meal.components).selectinload(
  MealRecipe.recipe).selectinload(Recipe.recipe_book)`.

Fuzzy tiers return `ingredients=[]` on the response models (raw-SQL
tier doesn't hydrate ORM) — no lazy-load risk.

## MCP tool

`mcp_server/tools/search.py::unified_search` is now `async def` and
dispatches through `await call_endpoint_async(UnifiedSearch, ...)`.
`mcp_server/test_search_tools.py` patches
`mcp_server.tools.search.call_endpoint_async` with `new_callable=
AsyncMock` and awaits the tool.

## Pre/post latency capture

Single-user traffic on `/v1/search` is too thin for a 24h p95 delta to
be statistically meaningful. Per the epic's rule #9 (party-mode
2026-04-23), the post-merge evidence will come from the
client-latency pipeline (`cla-*`) once the search screen sees a load
burst.

The conversion is mechanical (sync → async, no business-logic
change) and the endpoint is uniformly sub-100ms server-side today, so
the primary risk isn't latency — it's lazy-load / MissingGreenlet
regressions, which the audit above is the gate for.

## Rollback

One-line revert of the router-registration swap isn't meaningful here
because we flipped the domain directly (matches the aam-10 meal
pattern). If a regression shows up in production, revert commit is a
`git revert` of this story's single commit + `bin/prod-deploy`
(~10 min). The sync `Endpoint` base class still exists for other
not-yet-converted domains, so both halves keep building.

## Gotchas discovered during implementation

- `test_search_tools.py` also required the patch-path swap
  (`call_endpoint` → `call_endpoint_async`) plus `async def` + `await`.
  It's in a sibling `tests/mcp_server/` directory — not in the story's
  original File List, but still inside the search domain's test
  footprint.
- `count_queries(mock_async_db)` works unchanged: the helper reads
  `.db.execute.call_count` which AsyncMock updates on each await.
- `_sync_generate_query_embedding` is a `@staticmethod` on the
  UnifiedSearch class (not a module-level function) so test fixtures
  that patch on `UnifiedSearch._generate_query_embedding` keep working
  without changing import paths.
