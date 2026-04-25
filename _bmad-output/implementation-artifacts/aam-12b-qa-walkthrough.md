# aam-12b QA Walkthrough — Recipe Writes Async

**Story**: aam-12b (Recipe-domain writes async)
**Epic**: epic-api-async-migration
**Rollback procedure**: `git revert <aam-12b-commits> && bin/prod-deploy`
(~10 min). aam-12b does **not** mount a `/_legacy_v1/recipes` sibling —
see Section 4.

Sections:

1. Notification fan-out audit
2. Per-endpoint smoke + curl
3. Manual scenario checklist
4. Dual-register deviation call-out + cross-domain blast radius

---

## 1. Notification fan-out audit

Three write endpoints fan out push notifications. With AsyncEndpoint we
can no longer call sync `notify_*` functions inline — they would either
block the event loop or open a fresh sync session against the wrong
context. Every notification now goes through
`notify_via_threadpool(fn, **kwargs)` which schedules the helper on a
thread, where it gets a fresh sync `Database(db=SessionLocal())`.

| Endpoint                | Helper                       | Trigger condition                                  |
|-------------------------|------------------------------|----------------------------------------------------|
| `POST /v1/recipes`      | `notify_recipe_added`        | book `is_shared` after the recipe lands            |
| `POST /.../notes`       | `notify_recipe_note_added`   | every successful note write                        |
| `POST /.../fork`        | `notify_recipe_forked`       | after the fork commits + the new recipe id is read |

### 1.1 Audit query after each smoke

After exercising any of the three flows in prod, confirm no
`service="push_notifications"` errors landed by drilling
`error_logs`:

```bash
DATABASE_URL=<prod-url> python services/api/scripts/audit_errors.py \
    --drill push_notifications: --window 1h --format json
```

Expected: empty (or only entries with the same `request_id` as a
deliberate test where the FCM token was missing).

### 1.2 ForkRecipe re-fetch contract

`fork_recipe` is the only handler that re-fetches `source_recipe` and
`target_book` *after* `endpoint.run()` returns, then hands those ORM
objects to the sync `notify_recipe_forked` via `notify_via_threadpool`.
Because the async session is configured with `expire_on_commit=False`
and the helper only reads scalar attributes
(`name`, `id`, `recipe_book_id`), the cross-session attribute access is
safe. Verified in
`services/api/src/routers/v1/recipe_router.py::fork_recipe`.

---

## 2. Per-endpoint smoke

Run against staging or a freshly-migrated dev DB. Each block: curl,
expected status, post-call audit drill.

### 2.1 `POST /v1/recipe-books/{book_id}/recipes`

```bash
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"async smoke","ingredients":[{"name":"butter","quantity":1,"unit":"tbsp"}]}' \
  https://api.palateful.app/v1/recipe-books/$BOOK_ID/recipes | jq .id
```

Expected: 201, response body shape unchanged from sync, `embedding`
populated when OpenAI key is live.

### 2.2 `PUT /v1/recipes/{id}`

```bash
curl -sS -X PUT \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"renamed","ingredients":[]}' \
  https://api.palateful.app/v1/recipes/$RECIPE_ID
```

Expected: 200, `version_count` increments, snapshot row visible via
`GET /v1/recipes/$RECIPE_ID/versions`.

### 2.3 `DELETE /v1/recipes/{id}` (soft delete)

```bash
curl -sS -X DELETE -H "Authorization: Bearer $TOKEN" \
  https://api.palateful.app/v1/recipes/$RECIPE_ID
```

Expected: 200 `{success: true}`. `archived_at` populated; subsequent
`GET /v1/recipes/$RECIPE_ID` returns 404.

### 2.4 `POST /v1/recipes/{id}/restore`

```bash
curl -sS -X POST -H "Authorization: Bearer $TOKEN" \
  https://api.palateful.app/v1/recipes/$RECIPE_ID/restore
```

Expected: 200, `archived_at` cleared.

### 2.5 `POST /v1/recipes/{id}/fork`

```bash
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"destination_book_id\":\"$DEST_BOOK\"}" \
  https://api.palateful.app/v1/recipes/$RECIPE_ID/fork
```

Expected: 201, `forked_from_recipe_id`, `forked_from_book_id`,
`forked_from_recipe_name`, `forked_from_book_name` populated;
`notify_recipe_forked` fires (drill push_notifications).

### 2.6 `POST /v1/recipes/{id}/copy`

```bash
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"destination_book_id\":\"$DEST_BOOK\"}" \
  https://api.palateful.app/v1/recipes/$RECIPE_ID/copy
```

Expected: 201. Copy is identical to fork minus the lineage fields.

### 2.7 `POST /v1/recipes/{id}/move`

```bash
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"destination_book_id\":\"$DEST_BOOK\"}" \
  https://api.palateful.app/v1/recipes/$RECIPE_ID/move
```

Expected: 200, `recipe_book_id` updated.

### 2.8 `POST /v1/recipes/{id}/notes`

```bash
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"body":"great with extra garlic"}' \
  https://api.palateful.app/v1/recipes/$RECIPE_ID/notes
```

Expected: 201; `notify_recipe_note_added` fires.

### 2.9 `DELETE /v1/recipes/{id}/notes/{note_id}`

```bash
curl -sS -X DELETE -H "Authorization: Bearer $TOKEN" \
  https://api.palateful.app/v1/recipes/$RECIPE_ID/notes/$NOTE_ID
```

Expected: 200 `{deleted: true}`.

### 2.10 `POST /v1/recipes/{id}/versions/{version_id}/restore`

```bash
curl -sS -X POST -H "Authorization: Bearer $TOKEN" \
  https://api.palateful.app/v1/recipes/$RECIPE_ID/versions/$VERSION_ID/restore
```

Expected: 200, recipe state matches the snapshot, a fresh version row
landed with `changed_fields=["restore:<n>"]`.

### 2.11 Bulk endpoints (move / archive / tags)

```bash
# Bulk move
curl -sS -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"recipe_ids\":[\"$R1\",\"$R2\"],\"destination_book_id\":\"$DEST\"}" \
  https://api.palateful.app/v1/recipes/bulk/move

# Bulk archive
curl -sS -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"recipe_ids\":[\"$R1\"]}" \
  https://api.palateful.app/v1/recipes/bulk/archive

# Bulk tag update
curl -sS -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"recipe_ids\":[\"$R1\"],\"add_tags\":[\"weeknight\"],\"remove_tags\":[\"draft\"]}" \
  https://api.palateful.app/v1/recipes/bulk/tags
```

Expected: 200 with `moved_count` / `archived_count` / `updated_count`.

---

## 3. Manual scenario checklist

- [ ] Create + edit + delete + restore a recipe round-trip in the
      Flutter app — recipe appears, edits persist, soft-delete hides
      it from the list, restore brings it back.
- [ ] Fork a shared recipe into your own book; confirm the recipient
      receives a push (or an
      `audit_errors.py --drill push_notifications:` row recording the
      attempt).
- [ ] Add a note on a friend's shared recipe; confirm the book owner
      sees a push for `recipe_note_added`.
- [ ] Bulk archive 3+ recipes through the long-press multi-select on
      mobile.
- [ ] Restore a previous version; confirm the snapshot fields land on
      the live row and a *new* version row was appended.
- [ ] MCP write tools — `create_recipe` / `update_recipe` /
      `delete_recipe` / `fork_recipe` invoked through the assistant
      respond identically to the HTTP route (no double-`await`,
      no validation regression, no context-manager warning).

---

## 4. Dual-register deviation + cross-domain blast radius

aam-12b does **not** mount a `/_legacy_v1/recipes` sibling router.
Justification:
- Single-user prod traffic; there is no third-party write traffic to
  protect from a one-flip async migration.
- Rollback path (`git revert <aam-12b-commits> && bin/prod-deploy`)
  takes ~10 minutes, well under the next user request burst.
- Read endpoints already shipped without a sibling (aam-12a) — there
  is no architectural reason to gate writes harder.

### Cross-domain blast radius

- `services/worker/` — no imports of recipe write endpoints. Verified
  by:

```bash
rg -n 'api\.v1\.recipe\.(create_recipe|update_recipe|delete_recipe|fork_recipe|copy_recipe|move_recipe|add_recipe_note|delete_recipe_note|restore_recipe|restore_recipe_version|bulk_)' services/worker/
```

  Empty.

- `libraries/utils/utils/services/meal_service.py` and
  `aggregate_meal_ingredients` — untouched. They keep their sync
  signature (worker contract) and continue to be called from sync
  worker tasks.
- `test_recipe_book.py`, `test_meal.py`, etc. — untouched; aam-10 /
  aam-11 already converted those domains.

### Coverage gate

After aam-12b lands, the recipe write endpoints + the MCP write tools
are pinned at 100% line + branch coverage:

```bash
DATABASE_URL=<test-url> poetry run pytest \
  tests/test_recipe.py tests/test_fork_recipe.py \
  tests/test_recipe_ingredient_input.py tests/mcp_server/test_recipes.py \
  --cov=src/api/v1/recipe --cov=src/mcp_server/tools/recipes \
  --cov-report=term-missing
```

Expected: 100% on every endpoint in the AC list, 100% on
`src/mcp_server/tools/recipes.py`.
