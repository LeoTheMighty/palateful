<!-- refined via party-mode 2026-04-25 (consolidated) -->
# Epic: Recipe Default Books — `Favorites` (virtual) + `Trying Out` (system)

## Overview

Seed every Palateful user with two opinionated default books — `Favorites` and `Trying Out` — and route share-import recipes into `Trying Out` by default. This unblocks the rest of the recipe-organization workstream by giving the curation surfaces (book switcher, share router, bulk-organize action bar) consistent system-pinned destinations to point at, without introducing a new lifecycle column or a parallel data model.

## Goal

Make "I'm trying this one out" and "I want to favorite this without cluttering my real books" first-class flows by leaning on the existing `RecipeBook` primitive plus the existing `user_favorites` flag, asymmetrically. Defer any decision about a third primitive (lifecycle, tags) until users ask for it.

## End-user flow

1. **New user signs up** → onboarding completes → backend creates one `Trying Out` recipe book for them and sets `user.default_recipe_book_id = trying_out.id`.
2. **Existing user opens the app after the migration ships** → backend has back-filled one `Trying Out` book per user; their existing `default_recipe_book_id` is left as-is. Their first launch shows `Trying Out` pinned in the book switcher next to their existing books.
3. **User opens the recipe-books switcher** (book icon on home header, or in the side drawer) → sees a top section labeled **System** with two pinned entries: ❤️ **Favorites** and 📒 **Trying Out**, then a divider, then their personal books.
4. **User taps Favorites** → recipe list renders all recipes where `user_favorites.user_id = me AND user_favorites.archived_at IS NULL`, regardless of which real book each recipe lives in. Same data set as today's home-screen favorites carousel, just now reachable as a "book."
5. **User taps Trying Out** → recipe list renders all recipes with `recipe_book_id = my_trying_out_book.id AND archived_at IS NULL`. Real book, real FK, behaves like every other book except for the system icon and the default-share routing.
6. **User imports a recipe via share-sheet, photo, or URL paste** without picking a destination book → it lands in `Trying Out`. (If the user explicitly picks a different book in the import flow, that pick wins.)
7. **User can favorite any recipe from any book** → recipe shows up in the Favorites view in addition to its real book. Unchanged from today.
8. **User cannot delete or rename Trying Out** in v1. They *can* hide it from the switcher via a per-user preference (deferred to a follow-up if requested; v1 = always pinned).

## Frontend changes

- `app/lib/features/recipe_books/recipe_book_switcher.dart` (or wherever the switcher lives — confirm in story `recipe-defaults-2`): pin the two system entries at the top with a divider; pull `Favorites` from the existing favorites filter (no API change) and `Trying Out` from the new `is_system=true` book.
- New widget `SystemBookTile` (icon + label + count) — shared between both system entries; styled distinctly from user-created books (lighter background, system icon prefix).
- `app/lib/features/recipes/add_recipe/receive_import_screen.dart:209-219` — when no `bookId` query param, fall through to `_authService.defaultRecipeBookId` (already does this); the only visible change is that for new users that default is now `Trying Out`. For existing users, no behavior change unless they had no default set.
- Onboarding flow (`1-4-onboarding-flow` already done): no UI changes — backend seeds `Trying Out` and sets `default_recipe_book_id` server-side after first user creation. Confirm the existing onboarding flow doesn't override `default_recipe_book_id` after signup.
- Empty-state copy on Trying Out: "Recipes you're testing land here. Move them to Favorites or one of your books once you decide."

## Backend changes

- **Alembic migration** (`services/migrator/`):
  - Add `is_system: Mapped[bool] = mapped_column(default=False, nullable=False, server_default=sa.false())` to `recipe_books`.
  - Add a partial unique index `ix_recipe_books_one_system_per_user_per_kind` on `(user_id, name)` `WHERE is_system=true` to prevent accidental duplicate seeding.
  - Data migration: for each existing `users.id`, insert one `recipe_books` row with `name='Trying Out'`, `is_system=true`, `is_public=false`, `is_shared=false`. Idempotent on re-run.
- **Recipe-book model** (`libraries/utils/utils/models/recipe_book.py`): add `is_system: Mapped[bool]` field.
- **User-creation hook** (`services/api/src/api/v1/auth/` or wherever new-user provisioning happens — confirm in story `recipe-defaults-1`): on first user-record creation, create the system Trying Out book and set `default_recipe_book_id` to it. Wrapped in a single transaction with the user insert.
- **Share/import default routing** (`services/api/src/api/v1/import_job/start_import_job.py` or equivalent): no change needed — the existing `default_recipe_book_id` field is the source of truth, we're just making sure new users have it set to Trying Out. Audit the few call sites that bypass the default and pick a static "ungrouped" or first-book.
- **Recipe-book list endpoint** (`GET /v1/recipe-books`): returns `is_system` in each row. Optional: separate them server-side into `system_books` and `user_books` arrays in the response, or let the client sort by `is_system DESC`. Pick whichever keeps the response shape additive and Flutter-side simple.
- **Guard rails** on `DELETE /v1/recipe-books/{id}` and `PATCH …`: 400 if `is_system=true`. Mirror existing archive guard.

## Infrastructure changes

None. Pure Postgres migration via existing migrator; no new env vars; no new AWS resources; no new pip deps.

## Initial design principles (from research + party-mode)

- **Asymmetry is deliberate.** Favorites stays a virtual lens because the existing `user_favorites` flag is *already* the right primitive for "this is great regardless of where it lives." Trying Out is a real book because share-imports need a real FK destination.
- **Existing `default_recipe_book_id` is reused, not replaced.** No parallel "system default" field. New users get it set to the seeded Trying Out; existing users keep whatever they had.
- **Idempotent seeding.** Running the data migration twice does nothing the second time. New-user hook checks for existing system books before seeding.
- **No retroactive favoriting / moving.** Migration does not touch existing recipes' book membership or favorite state.

## File structure

```
libraries/utils/utils/models/
  recipe_book.py                         # MODIFY — add `is_system` column
services/migrator/migrations/versions/
  XXXX_add_is_system_and_seed_trying_out.py   # NEW
services/api/src/
  api/v1/auth/<new-user-provisioning>.py # MODIFY — seed Trying Out + set default
  api/v1/recipe_book/list_recipe_books.py # MODIFY — include `is_system` in response
  api/v1/recipe_book/_update.py / _delete.py # MODIFY — guard against is_system mutation
app/lib/features/recipe_books/
  recipe_book_switcher.dart              # MODIFY — pin system books
  system_book_tile.dart                  # NEW
app/lib/features/recipes/add_recipe/
  receive_import_screen.dart             # AUDIT — confirm default-book fallback path
```

## Stories

### `recipe-defaults-1` — Backend: `is_system` column + Trying Out seed migration

**As** the system,
**I want to** add an `is_system` Boolean to `recipe_books` and seed one `Trying Out` book per existing user,
**So that** the new-user provisioning hook and bulk-organize features have a stable system-book primitive to reference.

**Acceptance:**
- Alembic migration adds `is_system` column with `default=false`, `nullable=false`, `server_default=false()`.
- Data migration inserts exactly one `Trying Out` book for every existing user that doesn't already have one (idempotent).
- `recipe_books` model exposes `is_system`.
- `GET /v1/recipe-books` includes `is_system` in each row.
- Existing `default_recipe_book_id` is left untouched on existing users.
- Guard: `DELETE /v1/recipe-books/{id}` and `PATCH …` return 400 for `is_system=true` books.
- 100% line coverage on touched API code (per project gate).

### `recipe-defaults-2` — Backend: new-user provisioning hook seeds Trying Out + sets default

**As** a new user,
**I want** my first share-import or photo-import to land in a sensible default book,
**So that** I'm not asked to pick a destination on my first interaction.

**Acceptance:**
- New user-creation path (Auth0 callback → user row insert) creates one `Trying Out` book and sets `users.default_recipe_book_id` to its id, in the same transaction.
- Idempotent: re-running the hook for an existing user with a system Trying Out is a no-op.
- Test: full new-user flow (sign-up → Auth0 callback) ends with the user having `default_recipe_book_id` pointing at a `is_system=true` book named `Trying Out`.

### `recipe-defaults-3` — Frontend: switcher pins system books at top with distinct styling

**As** a user,
**I want** Favorites and Trying Out pinned at the top of the recipe-book switcher,
**So that** I know they're system entries and reach them in one tap.

**Acceptance:**
- Recipe-book switcher renders a `System` section above the user-books section with a divider.
- ❤️ Favorites tile uses the existing favorites-filter route (no new endpoint); Trying Out tile uses the new `is_system=true` book.
- Tapping Favorites shows the same recipe set as the home favorites carousel.
- Tapping Trying Out shows recipes filtered by `recipe_book_id = trying_out.id`.
- Long-press on either system tile does NOT offer rename/delete (system books are locked).
- Widget tests cover both system tiles' tap → list state.

### `recipe-defaults-4` — Frontend + audit: share-import fallback uses default_recipe_book_id consistently

**As** a user sharing a recipe in,
**I want** the recipe to land in Trying Out automatically,
**So that** I don't have to pick a book every time.

**Acceptance:**
- Share-sheet (`receive_import_screen.dart`), photo-import wizard, URL paste, and share-extension entry points all consult `defaultRecipeBookId` when no explicit destination is provided.
- For new users post-defaults-2, that default is Trying Out.
- For existing users with an existing default, behavior is unchanged.
- For existing users with no default set, the migration ensures `default_recipe_book_id` points at Trying Out (ideally via defaults-2 backfill, otherwise patched here).
- Manual smoke: fresh-account → share a recipe in → confirm it lands in Trying Out, visible in the switcher.

## Dependencies

- **Hard:** none. Foundation epic.
- **Soft:** `epic-recipe-list-organization`, `epic-recipe-bulk-organize`, `epic-import-duplicate-detection` all benefit from this landing first (they reference the system-book pinning and the default destination).

## Open questions for the user

None — all locked in the 2026-04-25 PRD addendum.

## Lenses (party-mode coverage check)

- **PM (John):** confirmed defaults are sized to deliver weekly value (Trying Out for share-import flow; Favorites for cross-cutting curation).
- **UX (Sally):** confirmed asymmetry (virtual Favorites + real Trying Out) is invisible to the end user — both look like books in the switcher, both behave like books on tap.
- **Backend (Winston):** confirmed reuse of `default_recipe_book_id` over a new column; idempotent migration; locked is_system guard.
- **Frontend (Amelia/UX):** confirmed Favorites needs no new endpoint — reuse the existing favorites filter.
- **QA (Quinn):** test plan covers new-user + existing-user back-fill + system-book mutation guards.
- **Infra:** None — no new resources.
