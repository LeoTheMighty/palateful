# aam-12a QA Walkthrough — Recipe Reads Async

**Story**: aam-12a (Recipe-domain reads + read-adjacent async)
**Epic**: epic-api-async-migration
**Rollback procedure**: `git revert <aam-12a-commits> && bin/prod-deploy` (~10 min). aam-12a does NOT mount a `/_legacy_v1/recipes` sibling — see Section 4.

This walkthrough has four sections, matching the runbook template:

1. Lazy-load audit
2. Pre-merge latency baseline
3. Manual scenario checklist
4. Dual-register deviation call-out + cross-domain blast radius

---

## 1. Lazy-load Audit

Unlike aam-10's meal domain, `build_recipe_response` and the read
endpoints are **scalar-query dominated** — no chain `recipe.<rel>.<rel>`
access outside the explicit query results. The `selectinload` burden is
therefore trivial.

### 1.1 Grep — attribute chains in `services/api/src/api/v1/recipe/` (read-side)

```bash
rg -nE 'recipe\.(recipe_book|ingredients|steps|notes|versions)\b' \
    services/api/src/api/v1/recipe/_response.py \
    services/api/src/api/v1/recipe/get_recipe.py \
    services/api/src/api/v1/recipe/list_recipes.py \
    services/api/src/api/v1/recipe/list_archived_recipes.py \
    services/api/src/api/v1/recipe/get_public_recipe.py \
    services/api/src/api/v1/recipe/get_public_recipe_by_token.py \
    services/api/src/api/v1/recipe/get_recipe_version.py \
    services/api/src/api/v1/recipe/get_recipe_versions.py \
    services/api/src/api/v1/recipe/get_photo_upload_url.py \
    services/api/src/api/v1/recipe/toggle_favorite.py \
    services/api/src/api/v1/recipe/share_recipe.py \
    services/api/src/api/v1/recipe/revoke_recipe_share.py \
    --glob '!*test*' --glob '!*__pycache__*'
```

**Expected**: **no results** — every `RecipeStep` / `RecipeIngredient` /
`UserFavorite` / `RecipeVersion` / `RecipeNote` read is a separate
explicit query that returns scalar columns, not a back-traversal off
the `Recipe` row.

### 1.2 Per-query coverage

| Query | Shape | Lazy-load risk |
|---|---|---|
| `await self.database.find_by(Recipe, id=...)` | single scalar row | none |
| `await self.database.find_by(RecipeBookUser, ...)` | single scalar row | none |
| `await self.database.where(RecipeStep, recipe_id=..., asc="step_number").all()` | list of `RecipeStep` (scalar columns only) | none |
| `await self.db.execute(select(RecipeIngredient, Ingredient).join(...).where(...))` | tuple of (RecipeIngredient, Ingredient) — `ingredient` preloaded via join | none — join materializes the Ingredient, no back-traversal |
| `await self.database.find_by(UserFavorite, ...)` | single scalar row | none |
| `await self.database.where(RecipeVersion, recipe_id=...).count()` | `SELECT COUNT(*)` | none |
| `await self.database.where(RecipeNote, recipe_id=..., asc="created_at").all()` | list of scalar `RecipeNote` rows | none |
| `await self.database.find_by(ImportItem, created_recipe_id=...)` (admin debug) | single scalar row | none |

### 1.3 pbq-3 fast path audit

`ListRecipes` preserves the bulk-favorite-join fast path:

```python
fav_result = await self.db.execute(
    select(UserFavorite.recipe_id).where(
        UserFavorite.user_id == user.id,
        UserFavorite.recipe_id.in_(recipe_ids),
    )
)
favorited_ids = set(fav_result.scalars().all())
```

One round-trip per page, not per-recipe. Identical shape to pre-aam-12a.

---

## 2. Pre-merge Latency Baseline

Capture a 24h p95 baseline before merging and diff after deploy using
`services/api/scripts/analyze_latency.py` (see CLAUDE.md for syntax):

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --window 24h --top 30 --format csv > /tmp/aam-12a-baseline.csv
```

Key endpoints to watch:

- `GET /v1/recipes/{recipe_id}` — p95 should not regress > 20%
- `GET /v1/recipe-books/{book_id}/recipes` — pbq-3 must keep list under ~100ms p95 for typical book size
- `POST /v1/recipes/{recipe_id}/favorite` — 3 DB round-trips, unchanged
- `GET /v1/recipes/public/{token}` — 2 `db.execute` + 1 `find_by` + 1 `where`; unchanged round-trip count
- `POST /v1/recipes/{recipe_id}/photo-upload-url` — AWS presign is now `await`ed on a threadpool; slightly lower latency expected (frees the event loop)

Post-deploy diff (after 24h of production traffic):

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --regression-hunt --format table
```

---

## 3. Manual Scenario Checklist

Run against a Flutter build + staging API after the `aam-12a` commits
have deployed. Each scenario exercises one of the 13 converted endpoints
plus the shared helper.

- [ ] **Recipe details page loads** — `GET /v1/recipes/{id}` returns
  ingredients (joined with Ingredient), steps, notes, version count.
  Is-favorite field reflects current user state.
- [ ] **Recipe list page loads** — `GET /v1/recipe-books/{book_id}/recipes`
  returns paginated items, total count, and per-item `is_favorite`
  populated from the pbq-3 bulk-favorite join (not per-recipe).
- [ ] **Search + vibe filter work** — `?search=` and `?vibe=` both
  narrow the list + total.
- [ ] **Archived recipes list** — `GET /v1/recipes/archived` returns
  every archived recipe across the user's book memberships, newest
  archive first.
- [ ] **Vibe options load** — `GET /v1/recipes/vibes/options` returns
  the static constant payload (no DB hit).
- [ ] **Public share by ID** — `GET /v1/recipes/{id}/public` works when
  the book is public; 404s otherwise.
- [ ] **Public share by token** — `GET /v1/recipes/public/{token}`
  returns the shared recipe; archived or unknown tokens 404.
- [ ] **Version history** — `GET /v1/recipes/{id}/versions` lists every
  version newest-first; each item has `version_number` + changed_fields.
- [ ] **Single version snapshot** — `GET /v1/recipes/{id}/versions/{ver}`
  returns the full snapshot JSON + changed_fields.
- [ ] **Photo upload URL** — `POST /v1/recipes/{id}/photo-upload-url`
  returns a presigned URL (now generated via the async boto3 wrapper
  from aam-9). File upload via the returned URL succeeds.
- [ ] **Toggle favorite add** — `POST /v1/recipes/{id}/favorite` on an
  unfavorited recipe returns 201 with `is_favorite=true` and the full
  recipe payload. Row inserted in `user_favorites`.
- [ ] **Toggle favorite remove** — Same endpoint on a favorited recipe
  returns 200 with `is_favorite=false`. Row removed.
- [ ] **Share recipe** — `POST /v1/recipes/{id}/share` returns 201 with
  token + deep-link; `recipe.share_token` populated in DB.
- [ ] **Revoke recipe share** — `DELETE /v1/recipes/{id}/share` returns
  200 `{success: true}`; `recipe.share_token` cleared.
- [ ] **MCP `get_recipe` tool** — LLM asks "what's in my Pasta recipe?"
  and the tool returns the full recipe via `call_endpoint_async`.
- [ ] **MCP `list_recipes` tool** — LLM asks "show me recipes in my
  Weeknight book" and the tool returns a paginated list.
- [ ] **MCP `toggle_favorite` tool** — LLM says "favorite the Pasta
  recipe" and the state flips; follow-up `list_favorites` shows it.

### 3.1 Negative scenarios

- [ ] **Recipe not found** — `GET /v1/recipes/bogus-id` returns 404.
- [ ] **Recipe book access denied** — `GET /v1/recipes/{id}` for a
  recipe in a book the user isn't a member of returns 403.
- [ ] **Unauthenticated request to authed endpoints** returns 401/422.
- [ ] **Public endpoints work without auth** — same token returns 200
  from an unauth'd client.

---

## 4. Dual-register deviation + cross-domain blast radius

### 4.1 Deviation

aam-12a does **not** mount a `/_legacy_v1/recipes` sibling router.
Justification is identical to aam-10:

- Single-operator traffic; a forced rollback window of ~10 min (single
  `git revert <aam-12a-commits> && bin/prod-deploy`) is acceptable.
- Maintaining dual registration doubles the surface area for any
  follow-up bug fix in `aam-12b` (write endpoints), since every write
  handler would need a sibling too.
- The recipe domain has no long-lived client sessions (unlike shopping
  list / meal WebSockets), so a fast roll-forward is the only fallback
  needed.

If the user decides to re-enable dual-register for subsequent stories
(aam-13+), the precedent set here is scoped to aam-12a only.

### 4.2 Cross-domain blast radius

- `build_recipe_response` callers: `GetRecipe`, `ToggleFavorite`
  (both now async). aam-12b's `UpdateRecipe` will become the third
  caller — at which point it switches from its own `UpdateRecipe.Response`
  shape to `await build_recipe_response(...)`.
- `ListMealsUsingRecipe` and `ListFavorites` were already async from
  aam-10. aam-12a only audits them; no behavioral change.
- Recipe book endpoints (`aam-11`) and meal endpoints (`aam-10`) are
  already async — no impact.
- Worker paths (`services/worker/`) do NOT import any of the converted
  recipe files; verified via:
  ```bash
  rg -n 'from api\.v1\.recipe' services/worker/src/ || echo "no worker imports"
  ```

### 4.3 Contract-gate checklist

- [x] No sync `self.database.find_by / where / create / delete / save`
      calls remain in the converted files.
- [x] Every `await self.db.execute(...)` returns `MockExecuteResult`-
      compatible shape; test side_effects match handler query count.
- [x] `AsyncDatabase.create` / `.delete` commit internally — no extra
      `self.db.commit()` on the toggle-favorite flow.
- [x] `generate_presigned_upload_url_async` is awaited in
      `get_photo_upload_url.py`; sync variant no longer called.
- [x] Router handlers that still need `get_database` / `get_current_user`
      (sync) are the aam-12b write handlers only.
