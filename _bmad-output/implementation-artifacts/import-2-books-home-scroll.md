# Story Import.2: Books Horizontal Scroll on Home — Recency Sorting

Status: done

## Story

As a user,
I want my recipe books displayed as a horizontal scroll section at the top of the Home screen sorted by most recently opened,
so that my active books are always front-and-center without needing a dedicated tab.

## Acceptance Criteria

1. Home screen shows a "My Books" section above the recipe list with a horizontal scrolling row of book cards
2. Book cards show: book name, recipe count, star badge if default, and a thumbnail mosaic (top 3-4 recipe photos)
3. Books are sorted by `last_opened_at DESC NULLS LAST`
4. A "See All →" link in the section header navigates to the full Books list screen
5. A "+ New Book" card at the end of the scroll creates a new recipe book
6. Tapping a book card navigates to the book detail screen
7. `last_opened_at` is tracked per-user on the `recipe_book_users` join table
8. Viewing a book detail screen updates `last_opened_at` as a side effect (no extra API call)
9. New books get `last_opened_at = now()` on creation so they appear first

## Tasks / Subtasks

- [x] Task 1: Backend — add last_opened_at tracking (AC: #7, #8, #9)
  - [x] Migration: add `last_opened_at TIMESTAMPTZ` to `recipe_book_users` table (nullable)
  - [x] Update RecipeBookUser model in `libraries/utils/utils/models/recipe_book_user.py`
  - [x] In GET /recipe-books/{id} handler: update `last_opened_at = now()` on the RecipeBookUser row as side effect
  - [x] In POST /recipe-books (create): set `last_opened_at = now()` on the owner's RecipeBookUser row
  - [x] Update GET /recipe-books (list): order by `last_opened_at DESC NULLS LAST`, include `last_opened_at` in response

- [x] Task 2: Home screen — Books section UI (AC: #1, #2, #4, #5, #6)
  - [x] Add "My Books" section to Home screen above recipe list
  - [x] Section header: "My Books" text + "See All" tappable link
  - [x] Horizontal scroll (`ListView.builder` with `scrollDirection: Axis.horizontal`)
  - [x] Book card widget showing:
    - Book name (truncated if long)
    - Recipe count badge (e.g., "12 recipes")
    - Star icon if `is_default` (from defaults epic)
    - Placeholder icon (thumbnail mosaic deferred to polish story)
  - [x] Last card: "+ New Book" with add icon, triggers book creation flow
  - [x] Tapping a book card: `context.push('/recipe-books/${book.id}')

- [x] Task 3: Sorting by recency (AC: #3)
  - [x] Frontend: books already come sorted from API (Task 1)
  - [x] Books never opened appear at end (NULLS LAST)
  - [x] Newly created books appear first (last_opened_at = now() on create)

## Dev Notes

- The side-effect approach on GET /recipe-books/{id} means zero extra API calls from Flutter
- `recipe_book_users` is the join table — per-user tracking means shared book recency is independent per partner
- Book card height: ~120px, width: ~140px works well for horizontal scroll cards
- For the thumbnail mosaic: use the first 4 recipes' `photo_url` from the book's recipe list
- The GET /recipe-books list endpoint likely already loads recipes — check if photo URLs are included
- Default book star badge uses same visual pattern from the defaults epic

### References

- [Epic: epic-import-activity-nav.md]
