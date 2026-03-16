# Story 2.8: Archive & Restore Recipe Books

Status: done

## Story

As a user,
I want to archive entire recipe books I no longer need active,
so that my Books tab stays uncluttered without losing any recipes or data.

## Acceptance Criteria

1. Given I own a recipe book, when I archive the book, then it is removed from the active Books tab
2. All contained recipes are preserved (not individually archived)
3. I can view archived books in an archive section
4. I can restore an archived book, bringing it and all its recipes back to active status

## Tasks / Subtasks

- [x] Task 1: Create ArchiveRecipeBook endpoint (AC: #1, #2)
  - [x] Create `services/api/src/api/v1/recipe_book/archive_recipe_book.py` — `ArchiveRecipeBook(Endpoint)`, `POST /v1/recipe-books/{recipe_book_id}/archive`. Owner-only. Sets `archived_at = datetime.now(UTC)` on book. Recipes remain untouched (not individually archived).
  - [x] Register in `services/api/src/api/v1/recipe_book/__init__.py`
  - [x] Add route in `services/api/src/routers/v1/recipe_book_router.py` — MUST be before `/{recipe_book_id}` routes

- [x] Task 2: Create RestoreRecipeBook endpoint (AC: #4)
  - [x] Create `services/api/src/api/v1/recipe_book/restore_recipe_book.py` — `RestoreRecipeBook(Endpoint)`, `POST /v1/recipe-books/{recipe_book_id}/restore`. Owner-only. Uses `include_archived=True` to find, clears `archived_at`. Validates book is actually archived.
  - [x] Register in `__init__.py` and router

- [x] Task 3: Create ListArchivedRecipeBooks endpoint (AC: #3)
  - [x] Create `services/api/src/api/v1/recipe_book/list_archived_recipe_books.py` — `ListArchivedRecipeBooks(Endpoint)`, `GET /v1/recipe-books/archived`. Query archived books where user is a member. Include recipe count. Order by archived_at desc.
  - [x] Register in `__init__.py` and router — route MUST be before `/{recipe_book_id}`

- [x] Task 4: Filter archived books from ListRecipeBooks (AC: #1)
  - [x] Add `RecipeBook.archived_at.is_(None)` filter to the query in `list_recipe_books.py`

- [x] Task 5: Flutter API client methods
  - [x] Add `archiveRecipeBook(String id)` to `ApiClient`
  - [x] Add `restoreRecipeBook(String id)` to `ApiClient`
  - [x] Add `getArchivedRecipeBooks()` to `ApiClient`

- [x] Task 6: Flutter UI — Archive action in book detail screen (AC: #1)
  - [x] In `recipe_book_detail_screen.dart`, change popup menu: rename "Delete" to "Archive" with archive icon, keep destructive styling
  - [x] Archive action: confirmation dialog → call `archiveRecipeBook()` → pop back to books list

- [x] Task 7: Flutter UI — Archived books screen (AC: #3, #4)
  - [x] Add "Archived Books" entry point in `recipe_books_screen.dart` (e.g., AppBar action or bottom of list)
  - [x] Show archived books list with restore action
  - [x] Restore: call `restoreRecipeBook()` → remove from list → show snackbar

- [x] Task 8: Backend tests
  - [x] Test ArchiveRecipeBook (success, not owner, not found, already archived)
  - [x] Test RestoreRecipeBook (success, not owner, not found, not archived)
  - [x] Test ListArchivedRecipeBooks (empty, with results)
  - [x] Test ListRecipeBooks filters out archived books

## Dev Notes

### Critical Context: This Is a Brownfield Story

All recipe book CRUD is complete (Story 2.2). Recipe archive/restore exists (Story 2.5). The `RecipeBook` model inherits `archived_at` from `Base → JoinsBase`, so no migration needed. The `Database.find_by()` defaults `include_archived=False`, so archived books are already invisible to `find_by` lookups.

### Key Design Decisions

**Archive, not Delete:** This story adds soft-delete (archive) for recipe books. The existing hard-delete (`DeleteRecipeBook`) remains available but we'll replace the UI-facing "Delete" with "Archive" in the book detail screen. Hard delete stays in the API for admin/cleanup purposes.

**Recipes stay untouched:** When a book is archived, its recipes are NOT individually archived. They simply become inaccessible because their parent book is hidden. On restore, all recipes reappear automatically.

**Owner-only:** Archive and restore require `owner` role (matching the existing `DeleteRecipeBook` permission).

### Route Ordering — CRITICAL

`GET /recipe-books/archived` MUST be before `GET /recipe-books/{recipe_book_id}` to avoid FastAPI treating "archived" as a recipe_book_id. Similarly, `POST /recipe-books/{recipe_book_id}/archive` and `/restore` can go after the parameterized GET since they have different HTTP methods/sub-paths.

### Pattern References

- `delete_recipe.py` — Soft delete pattern (sets `archived_at`)
- `restore_recipe.py` — Restore pattern (`include_archived=True`, clears `archived_at`)
- `list_archived_recipes.py` — List archived pattern (query with `archived_at.isnot(None)`)
- `list_recipe_books.py` — Current book list (needs `archived_at.is_(None)` filter added)

## Code Review Action Items

### Review 1 — Adversarial Code Review (2026-03-15)

- [x] **MEDIUM — `ArchiveRecipeBook.find_by` uses default `include_archived=False`**: The `find_by(RecipeBook, id=...)` call filtered out already-archived books, making the `is_archived()` check unreachable dead code. Fixed: use `include_archived=True` so the proper 400 "already archived" error is returned.

### DO NOT:
- Archive individual recipes when archiving a book
- Create new migrations — `archived_at` already exists on `RecipeBook`
- Remove the hard-delete endpoint — keep it for API completeness
- Add bulk archive for books — single book archive is sufficient
