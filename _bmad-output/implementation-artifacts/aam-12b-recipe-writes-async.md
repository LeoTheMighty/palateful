# Story aam-12b: Recipe writes async

**Status**: done
**Epic**: epic-api-async-migration
**Phase**: 3 — Per-domain conversions (split from aam-12)
**Depends on**: aam-12a (reads + `_response.py::build_recipe_response`
converted async; UpdateRecipe will `await` the same helper).

## Scope

aam-12b is the write half of the recipe-domain async conversion. The
13 write handlers and their `Endpoint` subclasses flip to
`AsyncEndpoint`, plus the 4 write-side MCP tools that still dispatch
through sync `call_endpoint`. aam-12a's already-converted read
endpoints and `_response.py` stay untouched.

Endpoints (13 — `services/api/src/api/v1/recipe/`):

- `create_recipe`
- `update_recipe`
- `delete_recipe`
- `fork_recipe`
- `copy_recipe`
- `move_recipe`
- `add_recipe_note`
- `delete_recipe_note`
- `restore_recipe`
- `restore_recipe_version`
- `bulk_move_recipes`
- `bulk_archive_recipes`
- `bulk_update_tags`

MCP tools (4 — `services/api/src/mcp_server/tools/recipes.py`):

- `create_recipe` — sync → async + `call_endpoint_async`.
- `update_recipe` — sync → async + `call_endpoint_async`.
- `delete_recipe` — sync → async + `call_endpoint_async`.
- `fork_recipe` — sync → async + `call_endpoint_async`.

Router handlers in `services/api/src/routers/v1/recipe_router.py` (13):
`create_recipe`, `update_recipe`, `delete_recipe`, `fork_recipe`,
`copy_recipe`, `move_recipe`, `add_recipe_note`, `delete_recipe_note`,
`restore_recipe`, `restore_recipe_version`, `bulk_move_recipes`,
`bulk_archive_recipes`, `bulk_update_tags`.

Notification fan-out fold-ins:
- `create_recipe` — `notify_recipe_added` via `notify_via_threadpool`
  when the book `is_shared`.
- `add_recipe_note` — `notify_recipe_note_added` via
  `notify_via_threadpool` on a successful note write.
- `fork_recipe` — `notify_recipe_forked` via `notify_via_threadpool`
  after the forked-recipe id is observed.

WebSocket broadcasts (`broadcast_event_to_recipe_book`) stay in the
router — they're already async-compatible and are fired post-`.call()`.

## Acceptance Criteria

1. All 13 write endpoint classes inherit `AsyncEndpoint`; `execute`
   becomes `async def`; every `self.db.*` / `self.database.*` call is
   `await`ed. Raw `self.db.query(...)` / `.scalar()` shapes are
   rewritten via `await self.db.execute(select(...))`.
2. `services/api/src/routers/v1/recipe_router.py`: the 13 write route
   handlers become `async def`, use
   `Depends(get_current_user_async)` + `Depends(get_async_database)`,
   and call `await Foo.call(...)`. Handlers that need the raw
   `{success, data, status}` dict (`add_recipe_note`, `fork_recipe`)
   use `await endpoint.run()` + `Foo.handle_result(result)` mirroring
   meal-event's `respond_to_invite` pattern.
3. All sync-only notification call sites in the router
   (`notify_recipe_added`, `notify_recipe_note_added`,
   `notify_recipe_forked`) are dispatched via
   `notify_via_threadpool(fn, ...)`. The `database` kwarg is not
   passed — the bridge injects a fresh sync `Database(db=SessionLocal())`.
4. `update_recipe`'s embedding-regeneration `self.database.db.commit()`
   becomes `await self.database.db.commit()`. `delete_recipe`,
   `move_recipe`, `restore_recipe`, `bulk_*` end-of-execute
   `self.database.db.commit()` calls become `await`ed.
5. `restore_recipe_version`'s `self.database.db.add(version)` is run
   against the async session; the final pre-commit `flush`/`commit`
   follows the AsyncDatabase convention (commit via
   `await self.database.db.commit()` is folded into the mutation pattern
   through `self.database.create(...)` / `.update(...)` wrappers where
   possible; the raw `.add(version)` inside `_create_version_snapshot`
   stays, with a single trailing `await self.database.db.commit()` at
   the end of the `execute` path, matching the existing sync ordering).
6. `fork_recipe` and `create_recipe` keep a single raw `.add()` /
   `.flush()` pattern for inline ingredient creation (per
   `epic-ingredients-string-simplification`). `self.database.db.add(...)`
   stays (the async session's `add` is sync) but flushes become
   `await self.database.db.flush()`.
7. `services/api/src/mcp_server/tools/recipes.py`: `create_recipe`,
   `update_recipe`, `delete_recipe`, `fork_recipe` tools become
   `async def` and dispatch via `await call_endpoint_async(...)`. The
   `_create_ingredient_for_name` helper grows an async twin
   (`_create_ingredient_for_name_async`) used by `create_recipe` /
   `update_recipe` — the sync helper is left in the file since it's
   exported in `__all__` and might be imported by tools that haven't
   converted yet.
8. Every MCP write tool resolves `database` via
   `get_current_database_async()` (not `get_current_database()`).
9. Write-side test classes in `test_recipe.py` (`TestCreateRecipe`,
   `TestDeleteRecipe`, `TestRestoreRecipe`, `TestCreateRecipeWithStepsAndTags`,
   `TestUpdateRecipeStepsAndTags` (only the update cases), `TestMoveRecipe`,
   `TestBulkUpdateTags`, `TestRestoreRecipeVersion`, `TestAddRecipeNote`,
   `TestDeleteRecipeNote`, `TestCreateRecipeMissingBranches`,
   `TestUpdateRecipeMissingBranches`, `TestRestoreRecipeVersionMissingBranches`,
   `TestAddRecipeNoteMissingBranches`, `TestDeleteRecipeNoteMissingBranches`,
   and `TestRecipeInferredFields` update-subset tests) are converted to
   the `mock_async_db` + `MockExecuteResult` pattern.
10. `test_fork_recipe.py` converted to `mock_async_db`.
11. `test_recipe_ingredient_input.py` converted to `mock_async_db`.
12. 100% API coverage preserved. If a converted line is hard to cover,
    pair-solve with a test — no new `# pragma: no cover` without a
    matching note here.
13. `sprint-status.yaml` flipped `aam-12b-recipe-writes-async: backlog
    → review` by the dev agent, then `review → done` by the code-review
    agent after findings are addressed.
14. Worker contract gate — `services/worker/` and
    `libraries/utils/utils/services/meal_service.py` /
    `aggregate_meal_ingredients` are **not touched**. Verified by grep
    that the worker never imports the converted write endpoints.

## Dual-register deviation

Same as aam-10 / aam-11 / aam-12a: this story does **not** mount a
`/_legacy_v1/recipes` sibling router. Justification identical —
single-user traffic, rollback via `git revert <aam-12b-commit> &&
bin/prod-deploy` (~10 min). Captured in the QA walkthrough.

## File List

### Modified

- `services/api/src/api/v1/recipe/create_recipe.py` — `AsyncEndpoint`;
  inline `Ingredient` creation uses `self.database.db.add(...)` +
  `await self.database.db.flush()`; `await self.database.create(...)` +
  `await self.database.db.commit()` for embedding/vibes write.
- `services/api/src/api/v1/recipe/update_recipe.py` — `AsyncEndpoint`;
  drops `self.database.db.refresh(recipe_ingredient)` (AsyncDatabase.create
  already refreshes); raw ingredient-join rewritten as
  `await self.db.execute(select(RecipeIngredient, Ingredient)...)`.
- `services/api/src/api/v1/recipe/delete_recipe.py` — `AsyncEndpoint`;
  `await self.database.db.commit()` on soft delete.
- `services/api/src/api/v1/recipe/fork_recipe.py` — `AsyncEndpoint`;
  async ingredient + step clones via `await self.database.create(...)`.
- `services/api/src/api/v1/recipe/copy_recipe.py` — `AsyncEndpoint`;
  identical shape to fork minus lineage fields.
- `services/api/src/api/v1/recipe/move_recipe.py` — `AsyncEndpoint`;
  `await self.database.db.commit()` at the end.
- `services/api/src/api/v1/recipe/add_recipe_note.py` — `AsyncEndpoint`.
- `services/api/src/api/v1/recipe/delete_recipe_note.py` —
  `AsyncEndpoint`; `await self.database.update(note, archived_at=...)`.
- `services/api/src/api/v1/recipe/restore_recipe.py` — `AsyncEndpoint`.
- `services/api/src/api/v1/recipe/restore_recipe_version.py` —
  `AsyncEndpoint`; `max_version` scalar via
  `await self.db.execute(select(func.max(...)))`; raw
  `self.db.query(RecipeIngredient, Ingredient).join(...)` rewritten as
  `await self.db.execute(select(...).join(...))`.
- `services/api/src/api/v1/recipe/bulk_move_recipes.py` — `AsyncEndpoint`.
- `services/api/src/api/v1/recipe/bulk_archive_recipes.py` — `AsyncEndpoint`.
- `services/api/src/api/v1/recipe/bulk_update_tags.py` — `AsyncEndpoint`.
- `services/api/src/routers/v1/recipe_router.py` — 13 write handlers
  flipped to async deps + `await Foo.call(...)`; notification sites
  routed through `notify_via_threadpool`. Imports drop
  `get_current_user`, `get_database`, and the direct-sync `Database`
  type where no longer used (keep if still referenced by the
  `get_public_recipe_book` sibling handler, which is owned by the
  recipe_book domain — already done in aam-11).
- `services/api/src/mcp_server/tools/recipes.py` — 4 write tools
  converted to `async def` + `await call_endpoint_async(...)`. Adds
  `_create_ingredient_for_name_async` helper.
- `services/api/tests/test_recipe.py` — write-side classes converted
  to `mock_async_db`. Mixed suites (e.g. `TestUpdateRecipeStepsAndTags`
  which has both reads and writes) have their write cases updated;
  read cases already migrated by aam-12a stay untouched.
- `services/api/tests/test_fork_recipe.py` — converted.
- `services/api/tests/test_recipe_ingredient_input.py` — converted.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` —
  `aam-12b-recipe-writes-async: backlog → review → done`.

### New

- `_bmad-output/implementation-artifacts/aam-12b-qa-walkthrough.md` —
  QA checklist + notification-path audit.

## Notes

- **normalize_unit_display**: stays sync (worker contract). Called
  from async endpoints (`create_recipe`, `update_recipe`,
  `fork_recipe`, `restore_recipe_version`) passing
  `self.database.db` (the `AsyncSession`). Pre-warmed module cache
  means no DB I/O on the hot path; the signature accepts the async
  session without runtime error because the session is only
  `.execute(...)`'d on cache miss — which doesn't happen in a
  healthy API process (cache warmed in `main.py` startup). Matches
  the pattern captured in `meal_service.aggregate_meal_ingredients`.
- **Version snapshot raw `self.db.add(version)`**: both
  `_create_version_snapshot` (update) and `_create_restore_snapshot`
  (restore) add directly to the session, and the enclosing `execute`
  flow committed later via `self.database.update(recipe, ...)` /
  `self.database.db.commit()`. Conversion: keep `.add(...)` as-is
  (async session's `add` is sync); ensure the trailing commit is
  awaited and happens at the end of `execute` so the version row
  lands in the same transaction as the mutation.
- **Ingredient inline creation**: `self.database.db.add(ingredient)`
  + `await self.database.db.flush()` matches the write pattern used
  by `join_shopping_list.py` (aam-13 area — already live).
- **update_recipe embedding commit**: the existing sync code calls
  `self.database.db.commit()` mid-execute to persist the embedding
  before the ingredient rewrites. Preserve ordering: commit the
  embedding write (`await self.database.db.commit()`), then proceed
  with ingredient/step rewrites (each of which commits via
  `AsyncDatabase.create` / `.delete` / `.update`). Coverage of this
  branch is already in `test_update_recipe_embedding_regeneration`.
- **fork_recipe / add_recipe_note router handlers**: mirror the
  `respond_to_invite` (meal_event) pattern — build the endpoint
  instance, `await endpoint.run()` for the raw dict, fire
  `notify_via_threadpool(...)` on success, then
  `handle_result(result)` at the return.
- **ForkRecipe's destination book name fetch**: the sync handler
  passed both `source_recipe` and `target_book` (looked up via
  `database.find_by`) to `notify_recipe_forked`. The converted
  notification sync helper still needs ORM objects — we pass the
  objects reloaded post-commit and rely on detached attrs (already
  eager-loaded by the time the endpoint returned).
- **MCP `_create_ingredient_for_name_async`**: needs to `await
  self.database.db.flush()` after `add(ingredient)` because the
  async session defers INSERT until flush/commit; no `refresh`
  required (the row's server default `id` is populated on `add` via
  the SQLAlchemy-side generator, same as sync).
- **Cross-domain blast radius**: `test_recipe_book.py`,
  `test_meal.py`, etc. untouched — the recipe-book and meal domains
  already landed their own async conversions (aam-11, aam-10).

## QA walkthrough placeholder

`_bmad-output/implementation-artifacts/aam-12b-qa-walkthrough.md`
will be generated alongside this story and list every endpoint's
happy-path curl, notification-fan-out verification steps
(`audit_errors.py --drill push_notifications:` after each), and the
`route_paint` p95 pre/post snapshot commands.
