# aam-15 — Pantry Domain Async

**Epic:** [epic-api-async-migration](../planning-artifacts/epic-api-async-migration.md)
**Status:** done
**Prerequisites landed:** aam-1..aam-6 (foundations), aam-foundations-notify-threadpool-helper, aam-9 (boto3 threadpool wrap), aam-10 (meal reference).

## Scope

Convert the pantry domain from sync `Endpoint` to `AsyncEndpoint`, matching the recipe laid out in
`_bmad-output/planning-artifacts/aam-phase1-dev-snippets.md`.

**Files in scope:**
- Router: `services/api/src/routers/v1/pantry_router.py` (5 handlers)
- Endpoints: `services/api/src/api/v1/pantry/*.py`
  - `get_default_pantry.py`
  - `add_ingredient.py`
  - `update_ingredient.py`
  - `delete_ingredient.py`
  - `estimate_expiry.py`
  - `helpers.py` — `require_pantry_access` + `format_pantry_ingredient`
- Service: `libraries/utils/utils/services/pantry_service.py` — async variants added alongside sync
  (sync variants MUST stay: `update_item.py` (aam-13 backlog) and `pantry_meal_subscriber.py` still
  use sync — their migrations are in different stories).
- Tests: `services/api/tests/test_pantry.py` rewritten to `mock_async_db` + `MockExecuteResult` pattern.

**Explicitly NOT in scope** (per ground-truth dev-snippets doc):
- `services/api/src/api/subscribers/pantry_meal_subscriber.py` — stays sync. It's called via the
  sync in-process dispatcher from `update_meal_event.py` which is still sync (aam-14 backlog). When
  aam-14 lands, the dispatch call wraps itself in `run_in_threadpool`; the subscriber stays sync
  until a future cleanup epic introduces the async dispatcher.
- `services/api/src/api/subscribers/pantry_shopping_subscriber.py` — pure logging body, no DB;
  sync dispatch from sync `update_item.py` (aam-13 backlog).
- `services/api/tests/test_pantry_meal_subscriber.py` — tests the sync subscriber directly;
  no HTTP, stays unchanged.
- `services/api/tests/test_pantry_shopping_subscriber.py` — pure logging smoke test; stays.
- `services/api/tests/test_update_item_pantry_hook.py` — exercises still-sync shopping_list flow.
- `services/api/tests/test_update_meal_event_pantry_hook.py` — exercises still-sync meal_event flow.

## Approach

### PantryService dual surface (temporary)

Because `update_item.py` (aam-13 backlog) and `pantry_meal_subscriber.py` still run synchronously,
the API of `utils.services.pantry_service` stays frozen on the sync path. We add async variants
alongside:

| sync (kept)                          | async (new)                                 | async caller                |
| ------------------------------------ | ------------------------------------------- | --------------------------- |
| `get_or_create_default_pantry`       | `get_or_create_default_pantry_async`        | `GetDefaultPantry`          |
| `upsert_pantry_ingredient`           | `upsert_pantry_ingredient_async`            | `AddPantryIngredient`       |
| `soft_delete_pantry_ingredient`      | `soft_delete_pantry_ingredient_async`       | `DeletePantryIngredient`    |
| `decrement_pantry_from_recipe`       | (not added — subscriber path only)          | —                           |

Cleanup epic will fold these back into the single async-only surface once every caller is async.

### Helpers (API layer)

`require_pantry_access` + `format_pantry_ingredient` live in
`services/api/src/api/v1/pantry/helpers.py`. Both get async variants:
- `require_pantry_access_async(user_id, pantry_id, database: AsyncDatabase, *, mutate: bool) -> PantryUser`
- `format_pantry_ingredient` stays shared (pure data-shaping, no DB work).

The sync `require_pantry_access` stays in place for symmetric reasons (future sync callers).

### Router flip

All 5 handlers flip to `async def` + `get_current_user_async` + `get_async_database` +
`return await X.call(...)`. Matches `meal_router.py` reference.

### Tests

`services/api/tests/test_pantry.py` rewritten top-to-bottom to the `mock_async_db` pattern:
- `mock_async_db.db.execute.side_effect = [MockExecuteResult(items=[...]), ...]`
- `mock_async_db.set_find_by(Model, result, **kwargs)` for `await self.database.find_by(...)` lookups
- All test names and intent preserved

## Acceptance Criteria

- [ ] 5 pantry endpoints inherit `AsyncEndpoint`, `async def execute`, queries use `select()` + `await`
- [ ] Router handlers are `async def` with `get_current_user_async` + `get_async_database`
- [ ] `pantry_service.py` adds `*_async` variants; sync variants unchanged (frozen for aam-13 + subscriber)
- [ ] `helpers.py` adds `require_pantry_access_async`; sync variant kept
- [ ] `test_pantry.py` rewritten to `mock_async_db` shape; every test name preserved; no test deletions
- [ ] Subscriber files + their test files UNCHANGED (out of scope)
- [ ] `npx nx run api:lint` green
- [ ] `npx nx run api:test` green with 100% coverage
- [ ] No sync DB call on the event loop inside any pantry handler (visual audit of the converted endpoint files)

## Out-of-Scope Callouts / Gotchas

- The sync `pantry_service.py` functions stay because `update_item.py` (aam-13) and
  `pantry_meal_subscriber.py` still import them. A premature rename/delete breaks those tests
  AND the live API at runtime.
- `estimate_pantry_expiry` only needs `database.find_by(Ingredient, ...)` and
  `require_pantry_access_async(..., mutate=False)` — it does not mutate. The sync
  `estimate_expires_at` itself takes no DB (pure function).
- MCP: there is no `services/api/src/mcp_server/tools/pantry.py`. Nothing to convert on the MCP
  side — skip the "MCP tool conversion" step from the snippets recipe.

## QA Walkthrough

See `aam-15-qa-walkthrough.md` (generated alongside this story).
