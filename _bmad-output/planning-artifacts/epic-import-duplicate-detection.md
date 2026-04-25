<!-- refined via party-mode 2026-04-25 (consolidated) -->
# Epic: Import Duplicate Detection — Approve-Import Knows You Already Have It

## Overview

When the user lands on the Approve-Import screen for a freshly parsed import item, the backend now checks whether the user already has a matching recipe in their library — by exact title match or by source URL — and surfaces the match with its current book or archive verdict. Three actions replace the default Approve button: **Skip**, **Restore** (if archived), **Add anyway**. The point: stop silently re-importing the same internet recipe every six months, and stop forcing the user to re-discover their own past judgment.

## Goal

Lift the user's archive verdict (and active library state) into the import flow so that "you already had this and you archived it" is a one-glance signal, not a memory test. Keep the v1 match scope tight (exact title + URL) — false positives are worse than the occasional silent duplicate we'll catch in a future fuzzy pass.

## End-user flow

1. **User taps a parsed import item** (text/PDF/photo/URL/share-sheet, any path) → Approve-Import screen renders the parsed recipe with editable fields (existing flow).
2. **Backend has already run a duplicate check** as part of the parse-completion pipeline (or on-demand when the screen loads — see backend section). Two match keys:
   - **Exact title** — `lower(trim(parsed.title)) == lower(trim(existing.title))` within the user's `recipes` rows.
   - **Source URL** — `parsed.source_url == existing.source_url` and both non-null. Applies to URL-imports (and to share-sheet imports that captured a URL).
3. **If no match,** the screen renders normally with the standard `Approve` button. No banner.
4. **If exactly one active (non-archived) match,** a **blue banner** above the recipe form reads: "*You already have **Mom's Brisket** — currently in **Mom's Recipes**, last cooked **3 days ago**.*" with three actions:
   - **Skip** (primary) — drops this import item (sets status to `skipped`); user is bounced back to the import-activity list.
   - **Add anyway** (secondary) — proceeds with the existing Approve flow (creates a new Recipe row).
   - (No Restore — recipe is already active.)
5. **If exactly one archived match,** an **amber banner** reads: "*You archived **Mom's Brisket** on 2024-03-12.*" with three actions:
   - **Restore** (primary) — un-archives the existing recipe, drops the import item.
   - **Skip** (secondary) — drops the import item, leaves the archived recipe archived.
   - **Add anyway** — proceeds with new-Recipe creation; user has both an archived original and a new active duplicate (their explicit choice).
6. **If multiple matches** (unlikely but possible — same title in two different books), the banner lists the top 3 with their books and a "Show all matches" affordance. Same three actions, applied to whichever match the user picks.
7. **Skip action records** — set `import_item.status = 'skipped'` (new state), preserve the parsed payload for audit.
8. **Tapping the matched recipe's name** in the banner deep-links to the existing recipe-detail screen — closing the import flow.

## Frontend changes

- **`approve_import_screen.dart`** (or wherever the Approve-Import UI lives — confirm in story `import-dup-1`): when the API response includes a `duplicate` block, render `DuplicateBanner` above the form; otherwise render existing UI.
- **New widget `DuplicateBanner`** — props: `match` (existing recipe summary: id, title, current_book_name, last_cooked, archived_at), `onSkip`, `onRestore` (null when not archived), `onAddAnyway`, `onTapMatchedRecipe`. Color follows state (blue active / amber archived).
- **Service: `ImportItemService`** — extend with `skipImportItem(itemId)` mapping to new backend endpoint.
- **Service: `RecipeService`** — already has `restoreRecipe`; reuse.
- **Reactivity**: skip and restore actions both invalidate the import-activity list via mutationBus events; restore additionally invalidates the relevant book's recipe list.
- **Empty/loading/error states**:
  - Loading: spinner over banner area until `duplicate` resolved.
  - Error fetching match details: degrade gracefully — render normal Approve flow with no banner; log to error_logs (`service="api"`).
- **Telemetry**: when banner shown, log `(match_kind: title|url, action: skip|restore|add_anyway)` for product feedback.

## Backend changes

- **Approve-Import response extension** (`GET /v1/import-items/{id}` or however the screen fetches the parsed item — confirm in story `import-dup-1`): include a `duplicate` block when match found:
  ```json
  {
    "duplicate": {
      "matches": [
        {
          "recipe_id": "...",
          "title": "Mom's Brisket",
          "current_book_id": "...",
          "current_book_name": "Mom's Recipes",
          "last_cooked": "2026-04-22T...Z",
          "archived_at": null,
          "match_kind": "title"  // or "source_url"
        }
      ]
    }
  }
  ```
- **Duplicate detection query** — runs on parse-completion (preferred — caches result in `import_items.duplicate_match_recipe_ids` JSONB column) OR on the GET above (simpler — runs every read). Decide in story `import-dup-2`.
  - Title match: `SELECT id, title, recipe_book_id, archived_at FROM recipes WHERE user_id = ? AND lower(trim(title)) = lower(trim(?))`. Indexed via existing user_id + lower(title) — confirm or add.
  - URL match: `SELECT … WHERE user_id = ? AND source_url = ?` (both non-null).
- **New endpoint: `POST /v1/import-items/{id}/skip`** — sets `status='skipped'`, preserves payload, returns the updated item.
- **New `ImportItemStatus` enum value: `skipped`** — alongside existing `pending`, `approved`, `rejected`, etc.
- **Last-cooked join** — reuse the same `MAX(cooking_logs.cooked_at)` pattern from `epic-recipe-list-organization`. Soft dependency: that epic's join helper can ship first or this epic ships its own thin version.
- **Authorization** — match query is scoped to the calling user's recipes only.
- **Performance** — title-match query must hit an index; under no circumstances scan the recipes table. Add `ix_recipes_user_lower_title` if missing.

## Infrastructure changes

None. (One small migration to add the `skipped` enum value + the index if missing.)

## Initial design principles (from research + party-mode)

- **Tight match scope in v1.** Exact title + URL only. Fuzzy matching (trigram, semantic) is a real feature but a v2 — false positives in v1 would erode trust.
- **Surface the verdict, don't relitigate.** If the user archived it, say so plainly; let them restore in one tap.
- **`Add anyway` is always available.** Users sometimes intentionally re-import (different version, different book). Don't block.
- **Skip preserves the parsed payload.** If we're wrong, the user can recover from import-activity history.
- **No silent dedup.** The backend never auto-skips; the *user* always sees the banner and chooses. Silent dedup hides bugs.

## File structure

```
app/lib/features/import/approve/
  approve_import_screen.dart             # MODIFY — render DuplicateBanner if response has it
  widgets/duplicate_banner.dart          # NEW
app/lib/services/
  import_item_service.dart               # MODIFY — skipImportItem method
services/api/src/api/v1/import_item/
  get_import_item.py                     # MODIFY — include `duplicate` block when match found
  skip_import_item.py                    # NEW
services/api/src/api/v1/import_item/
  _duplicate_match.py                    # NEW — match query helper, reused by approve & skip
libraries/utils/utils/models/
  import_item.py                         # MODIFY — `skipped` enum value (and optional cached duplicate ids JSONB)
services/migrator/migrations/versions/
  XXXX_add_skipped_status_and_title_index.py  # NEW
```

## Stories

### `import-dup-1` — Backend: duplicate-match query + response extension

**Acceptance:**
- New helper `find_duplicate_recipes(user_id, parsed_title, parsed_source_url)` returns 0+ matching recipe summaries (title or URL match), each including `recipe_id, title, current_book_id, current_book_name, archived_at, last_cooked`.
- `GET /v1/import-items/{id}` response includes a `duplicate.matches` array (empty if no match).
- Index `ix_recipes_user_lower_title` on `recipes (user_id, lower(trim(title)))` exists (added if missing).
- Performance: query p95 < 30ms on a user with 500 recipes (capture via test).
- 100% line coverage on touched code.

### `import-dup-2` — Backend: skip endpoint + `skipped` status

**Acceptance:**
- New enum value `ImportItemStatus.skipped` added (Alembic migration).
- `POST /v1/import-items/{id}/skip` endpoint sets status to `skipped`, returns the updated item, emits the appropriate mutationBus event.
- Authorization: only the import item's owner can skip; 403 otherwise.
- Idempotent: skipping an already-skipped item is a no-op (200 with current state).
- 100% line coverage maintained.

### `import-dup-3` — Frontend: DuplicateBanner + Approve-Import wiring

**Acceptance:**
- `DuplicateBanner` widget renders for each of: active-match (blue), archived-match (amber), multi-match (list with "Show all matches").
- Banner shows existing recipe title (tappable → recipe detail), current book name, last_cooked relative time, archive date if archived.
- Three buttons render appropriately based on archived state: Active = Skip / Add anyway; Archived = Restore / Skip / Add anyway.
- Skip → calls `ImportItemService.skipImportItem` → bounces user to import-activity list.
- Restore → calls `RecipeService.restoreRecipe` → also skips the import item → bounces back.
- Add anyway → proceeds with existing Approve flow.
- Widget tests cover all three banner states + all action paths.

### `import-dup-4` — Regression sweep + e2e

**Acceptance:**
- Standard Approve-Import flow with no duplicate is unchanged (no banner renders).
- Multi-match case: top 3 matches shown, "Show all matches" expands.
- e2e: import a recipe → archive it → re-import same recipe → confirm amber banner → tap Restore → confirm recipe is restored + import item skipped.
- e2e: import a recipe via URL → re-import same URL with different parsed title → confirm URL match still triggers the banner.
- Performance: Approve-Import screen first-paint not regressed > 100ms (the duplicate query is fast and runs server-side).

## Dependencies

- **Soft:** `epic-recipe-list-organization` (the last-cooked helper used in the response is shared) — order-independent if the helper is duplicated for v1.
- **Hard:** none.

## Open questions for the user

None — all locked in the 2026-04-25 PRD addendum.

## Lenses (party-mode coverage check)

- **PM (John):** confirmed three actions cover the realistic intent set (Skip / Restore / Add anyway); no fuzzy matching in v1.
- **UX (Sally):** confirmed banner color reflects state (blue active / amber archived); banner is non-modal so users can still edit fields below if they want to compare-then-decide.
- **Frontend (Amelia):** confirmed reuse of existing restoreRecipe; only one new endpoint (skip).
- **Backend (Winston):** locked the index requirement; locked computing duplicates server-side, never silently auto-skipping.
- **QA (Quinn):** test plan covers all three banner states, multi-match, idempotent skip, archive/restore round-trip.
- **Infra:** None.
