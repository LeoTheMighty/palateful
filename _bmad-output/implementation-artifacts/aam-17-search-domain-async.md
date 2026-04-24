# aam-17 — Search Domain Async

**Epic:** [epic-api-async-migration](../planning-artifacts/epic-api-async-migration.md)
**Status:** in-progress
**Prerequisites landed:** aam-1..aam-6 (foundations), aam-10 (meal reference), aam-15 (pantry reference).

## Scope

Convert the search domain from sync `Endpoint` to `AsyncEndpoint`, matching the recipe in
`_bmad-output/planning-artifacts/aam-phase1-dev-snippets.md`. Smallest domain chunk — a
single endpoint with one router handler and one MCP tool.

**Files in scope:**
- Endpoint: `services/api/src/api/v1/search/unified_search.py` — `UnifiedSearch`.
- Router: `services/api/src/routers/v1/search_router.py` — 1 handler (`GET /v1/search`).
- MCP tool: `services/api/src/mcp_server/tools/search.py` — `unified_search`.
- Tests: `services/api/tests/test_search.py` — rewritten to `mock_async_db` +
  `MockExecuteResult` pattern for `TestUnifiedSearch` + `TestUnifiedSearchDirect` +
  `TestUnifiedSearchQueryEmbedding`.

**Explicitly NOT in scope:**
- `services/api/src/api/v1/search/generate_recipe_embedding.py` — standalone helpers
  (`generate_recipe_embedding`, `assign_vibes_for_recipe`) consumed by still-sync recipe-write
  callers (aam-12b backlog, imports, worker). Leaving sync-only so those callers don't break.
- `TestGenerateRecipeEmbedding` + `TestAssignVibesForRecipe` classes in `test_search.py` —
  exercise the sync helpers above; no change.
- OpenAI client async swap — owned by aam-7 (Phase 2 cleanup). For this story, the sync
  OpenAI call inside `_generate_query_embedding` is dispatched through
  `run_in_threadpool` so the async event loop stays free (semantic tier only runs when
  exact + fuzzy don't fill the limit, so this path is rare but network-bound).

## Approach

### Endpoint class

`UnifiedSearch(Endpoint)` → `UnifiedSearch(AsyncEndpoint)`. `async def execute`. Every
private method that reads `self.db` becomes `async def` and awaits `self.db.execute(...)`.

Methods converted to `async def`:
- `execute`
- `_get_my_book_ids` (memoization preserved — cache key is still `self._my_book_ids`)
- `_search_my_recipes`
- `_search_public_recipes`
- `_search_my_recipes_fuzzy`
- `_search_public_recipes_fuzzy`
- `_search_my_recipes_semantic`
- `_search_public_recipes_semantic`
- `_search_my_meals`
- `_search_users`
- `_generate_query_embedding` (awaits `run_in_threadpool(_sync_openai)` wrapper)

Methods that stay `def` (no DB, no blocking I/O): `_recipe_matches`,
`_filter_conditions`, `_resolve_scope` (staticmethod), `_build_meal_search_result`.

Query translation follows the cheat-sheet in
`aam-phase1-dev-snippets.md`:
- `self.db.execute(stmt).scalars().all()` → `(await self.db.execute(stmt)).scalars().all()`
- `self.db.execute(stmt).all()` → `(await self.db.execute(stmt)).all()`

### Router flip

`search_router.py` handler flips to `async def` with `get_current_user_async` +
`get_async_database` + `return await UnifiedSearch.call(...)`. Matches `meal_router.py`.

### MCP tool flip

`mcp_server/tools/search.py::unified_search` becomes `async def` and dispatches through
`await call_endpoint_async(UnifiedSearch, ...)`.

### Tests

`test_search.py` classes that drive the HTTP path or the endpoint directly migrate from
`mock_db.db.query.return_value = MockQuery([...])` / `mock_db.db.execute.return_value =
MockExecuteResult([...])` → `mock_async_db.db.execute.side_effect = [...]` or `.return_value
= MockExecuteResult(...)`. Every test name and intent preserved; no deletions.

The helper-test classes (`TestGenerateRecipeEmbedding`, `TestAssignVibesForRecipe`) exercise
the sync standalone helpers and stay on the `mock_db` fixture untouched.

## Acceptance Criteria

- [ ] `UnifiedSearch` inherits `AsyncEndpoint`; `execute` + every `self.db`-touching method is `async def` with `select()` + `await`.
- [ ] `search_router.py` handler is `async def` using `get_current_user_async` + `get_async_database` + `return await UnifiedSearch.call(...)`.
- [ ] `mcp_server/tools/search.py::unified_search` is `async def` and calls `await call_endpoint_async(...)`.
- [ ] `generate_recipe_embedding.py` unchanged (sync helper kept for still-sync callers).
- [ ] `test_search.py` rewritten to `mock_async_db` shape; every test name preserved; no deletions.
- [ ] `npx nx run api:lint` green.
- [ ] `npx nx run api:test` green with 100% coverage.
- [ ] sprint-status: `aam-17-search-domain-async: backlog` → `review` → `done`.

## Out-of-Scope Callouts / Gotchas

- `_generate_query_embedding` wraps the sync OpenAI call via `run_in_threadpool` so the
  async event loop stays free until aam-7 does the `AsyncOpenAI` swap. Test for the
  method (`TestUnifiedSearchQueryEmbedding.test_generate_query_embedding_success`)
  now needs to `await` the result.
- `_search_my_recipes_fuzzy`, `_search_public_recipes_fuzzy`,
  `_search_my_recipes_semantic`, `_search_public_recipes_semantic` all have a
  `try: ... except Exception: return []` degrade path. Preserve verbatim — tests assert
  degrade-to-empty when `mock_async_db.db.execute.side_effect = Exception(...)`.
- Memoization on `_get_my_book_ids` — `getattr(self, "_my_book_ids", None)` cache check
  stays identical; the only shift is one `await` on the cache-miss branch.
- `count_queries(mock_db)` helper in `test_get_my_book_ids_memoized_across_tiers` — now
  points at `mock_async_db` because the endpoint issues `await mock_async_db.db.execute`.

## QA Walkthrough

See `aam-17-qa-walkthrough.md` (generated alongside this story).
