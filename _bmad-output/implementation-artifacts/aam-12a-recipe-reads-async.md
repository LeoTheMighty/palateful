# Story aam-12a: Recipe reads async

**Status**: done
**Epic**: epic-api-async-migration
**Phase**: 3 — Per-domain conversions (split from aam-12)

## Scope

aam-12a is the read/read-adjacent half of the recipe-domain async
conversion. aam-12b follows with the write endpoints + notification
fan-out. 12a must land first because it converts the shared
`_response.py::build_recipe_response` helper that 12b's `update_recipe`
consumes.

Endpoints (13):

- `get_recipe`, `list_recipes`, `list_archived_recipes`, `get_vibe_options`
- `get_public_recipe`, `get_public_recipe_by_token`
- `get_recipe_version`, `get_recipe_versions`
- `get_photo_upload_url`
- `toggle_favorite` (read-adjacent — mutates `UserFavorite` but response
  flows through `build_recipe_response`)
- `share_recipe`, `revoke_recipe_share`

Shared helper: `api/v1/recipe/_response.py::build_recipe_response` → async.

MCP tools (read-only): `get_recipe`, `list_recipes`, `toggle_favorite`.
`list_favorites` already async from aam-10; audit only.

## Acceptance Criteria

1. All 13 endpoints above inherit `AsyncEndpoint`; `execute` becomes async;
   every `self.db.*` / `self.database.*` call is `await`ed.
2. `api/v1/recipe/_response.py::build_recipe_response` becomes `async def`.
3. `api/v1/recipe/get_photo_upload_url.py` uses
   `_get_aws_service().generate_presigned_upload_url_async(...)` (aam-9
   async variant).
4. `api/v1/recipe/share_recipe.py` and `revoke_recipe_share.py` swap
   `self.db.commit()` / `refresh` → `await self.db.commit()` /
   `await self.db.refresh(...)`.
5. `services/api/src/routers/v1/recipe_router.py`: the 13 read/read-adjacent
   route handlers become `async def`, swap `Depends(get_database)` →
   `Depends(get_async_database)` and `Depends(get_current_user)` →
   `Depends(get_current_user_async)`, and prefix `return Foo.call(...)` →
   `return await Foo.call(...)`. Write handlers (aam-12b's scope) stay
   on the sync deps.
6. `services/api/src/mcp_server/tools/recipes.py`: `get_recipe`,
   `list_recipes`, `toggle_favorite` tools become `async def` and dispatch
   via `await call_endpoint_async(...)`.
7. `pbq-3` fast-path (bulk favorite join on `list_recipes.py:82–94`)
   preserved — converted to `await db.execute(select(...))` without a
   per-recipe extra round-trip.
8. Read-side test classes in `test_recipe.py` (`TestListRecipes`,
   `TestGetVibeOptions`, `TestGetRecipe`, `TestListArchivedRecipes`,
   `TestGetRecipePhotoUploadUrl`, `TestToggleFavorite`,
   `TestGetRecipeFavoriteField`, `TestGetRecipeIncludeParam`,
   `TestGetRecipeLeanDefault`, `TestGetRecipeVersion`,
   `TestGetRecipeVersionsMissingBranches`) plus all of `test_share_recipe.py`
   converted to `mock_async_db` + `db.execute.side_effect = [...]` pattern.
   `TestListFavorites` audited (already async from aam-10; no behavioral
   change expected).
9. 100% API coverage preserved.
10. Worker contract gate: worker paths don't import the converted recipe
    files — verified by grep.

## Dual-register deviation

Same as aam-10: this story does NOT mount a `/_legacy_v1/recipes` sibling
router. Justification identical — single-user traffic, rollback via
`git revert <aam-12a-commit> && bin/prod-deploy` (~10 min). Captured in
the QA walkthrough. The runbook's dual-register pattern returns for
subsequent domain stories if the user overrides per-story.

## File List

### Modified

- `services/api/src/api/v1/recipe/_response.py` — `build_recipe_response` async.
- `services/api/src/api/v1/recipe/get_recipe.py` — `GetRecipe(AsyncEndpoint)`; `await` all DB calls.
- `services/api/src/api/v1/recipe/list_recipes.py` — `ListRecipes(AsyncEndpoint)`; pbq-3 favorite-join preserved via `await db.execute(select(...))`.
- `services/api/src/api/v1/recipe/list_archived_recipes.py` — async.
- `services/api/src/api/v1/recipe/get_vibe_options.py` — async (trivial — no DB).
- `services/api/src/api/v1/recipe/get_public_recipe.py` — async.
- `services/api/src/api/v1/recipe/get_public_recipe_by_token.py` — async.
- `services/api/src/api/v1/recipe/get_recipe_version.py` — async.
- `services/api/src/api/v1/recipe/get_recipe_versions.py` — async.
- `services/api/src/api/v1/recipe/get_photo_upload_url.py` — async + `generate_presigned_upload_url_async`.
- `services/api/src/api/v1/recipe/toggle_favorite.py` — async + `await build_recipe_response(...)`.
- `services/api/src/api/v1/recipe/share_recipe.py` — async.
- `services/api/src/api/v1/recipe/revoke_recipe_share.py` — async.
- `services/api/src/routers/v1/recipe_router.py` — 13 handlers flipped to async deps + `await Foo.call(...)`.
- `services/api/src/mcp_server/tools/recipes.py` — 3 read tools async via `call_endpoint_async`.
- `services/api/tests/test_recipe.py` — read-side classes converted to `mock_async_db`.
- `services/api/tests/test_share_recipe.py` — converted.

### New

- `_bmad-output/implementation-artifacts/aam-12a-qa-walkthrough.md` — QA checklist + lazy-load audit.

## Notes

- **build_recipe_response** depends on: `RecipeStep`, `RecipeIngredient`
  (joined with `Ingredient`), `UserFavorite`, `RecipeVersion`,
  `RecipeNote`, optional `ImportItem` (admin-debug path). All are scalar
  queries or counts — no lazy-load chains, so no selectinload audit
  needed beyond verifying the builder's internal queries become awaited
  `self.database.where(...).all()` / `.count()`.
- **pbq-3 fast path** on `list_recipes`: the bulk favorite join is a
  single `SELECT recipe_id FROM user_favorites WHERE user_id = ? AND
  recipe_id IN (...)`. Rewritten inline via
  `await self.db.execute(select(UserFavorite.recipe_id).where(...))`,
  returning rows from `result.scalars().all()`. Shape identical.
- **share_recipe / revoke_recipe_share**: tiny endpoints that only flip
  `Recipe.share_token`. They don't hit `build_recipe_response`, so their
  async conversion is mechanical: `self.db.commit()` → `await self.db.commit()`.
- **get_vibe_options**: no DB at all — just reads a module-level constant.
  Converted to `AsyncEndpoint` purely so the router handler can use
  the async auth + DB deps consistently.
- **toggle_favorite**: AsyncDatabase.create/.delete commit internally,
  so the sync path's extra `self.db.commit()` after delete/add is dropped.
- **Write handlers stay sync**: `update_recipe`, `delete_recipe`,
  `create_recipe`, `fork_recipe`, `copy_recipe`, `move_recipe`,
  `bulk_*`, `add_recipe_note`, `delete_recipe_note`,
  `restore_recipe_version` all remain `Endpoint` subclasses with sync
  router handlers. aam-12b converts them.
- **Cross-domain blast radius**: `toggle_favorite` and `get_recipe` were
  the only callers of `build_recipe_response` — no external consumers.
  aam-12b's `update_recipe` will add the third call site at that time.
