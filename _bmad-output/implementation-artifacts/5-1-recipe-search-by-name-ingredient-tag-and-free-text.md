# Story 5.1: Recipe Search by Name, Ingredient, Tag & Free Text

Status: done

## Story

As a user,
I want to search my recipe collection by typing anything — a recipe name, an ingredient, a tag, or free text,
So that I can find what I'm looking for without knowing the exact title.

## Acceptance Criteria

1. Given I tap the search bar, When I type a query, Then results appear showing recipes matching by name, ingredient, tag, or free-text content
2. Results display as photo-dominant recipe cards consistent with the design system (not small list tiles)
3. Results return within 2 seconds at P95
4. An empty search shows a helpful prompt, not a blank screen
5. Search works across all recipes I have access to (personal + shared books)
6. Archived recipes do not appear in search results

## Tasks / Subtasks

- [x] Task 1: Add tag matching to backend `_recipe_matches()` (AC: #1, #6)
  - [x] Open `services/api/src/api/v1/search/unified_search.py`
  - [x] Add `func` to the SQLAlchemy import: `from sqlalchemy import exists, func, or_, select`
  - [x] In `_recipe_matches()`, add tag condition: `func.array_to_string(Recipe.tags, ',').ilike(f"%{query}%")`
  - [x] Extend the `or_()` call to include the tag condition as the fourth branch
  - [x] Verify `Recipe.tags` nullable handling: `array_to_string(NULL, ',')` returns NULL → `NULL ILIKE ...` is NULL (not True) → correct, no recipes with null tags will match

- [x] Task 2: Upgrade recipe cards in `SearchScreen` to photo-dominant layout (AC: #2)
  - [x] Open `app/lib/features/search/search_screen.dart`
  - [x] Replace `_buildRecipeTile()` method with a photo-dominant card layout:
    - Container/Card with image displayed at full width or left-half with ~120px height (not 48×48 thumbnail)
    - Recipe name prominent below/beside image at 16px bold
    - Secondary line: book name + total time
    - Optional tertiary line: first 3 ingredient names
  - [x] Use `ClipRRect(borderRadius: BorderRadius.circular(12), ...)` for image corners
  - [x] Show fallback icon in a themed container when no `image_url`
  - [x] Keep existing `onTap: () => context.push('/recipes/${recipe['id']}')`
  - [x] Keep `colorScheme.*` theming (do NOT switch to AppColors — search screen uses standard Material theme)

- [x] Task 3: Add tag search backend test (AC: #1 — tag branch)
  - [x] Open `services/api/tests/test_search.py`
  - [x] Add `test_search_by_tag()`: mock a recipe with `tags=['vegetarian']`, query `q=vegetarian`, verify result included
  - [x] Test must be a unit test using `mock_db` + `MockExecuteResult` pattern from conftest (do not require running DB)
  - [x] Note: due to mock abstraction, verify the method is called correctly rather than end-to-end tag matching

- [x] Task 4: Add/update frontend widget test for SearchScreen (AC: #2, #4)
  - [x] Open or create `app/test/search_screen_test.dart`
  - [x] Test: empty state shows helpful prompt (find `'Search your recipes'` text)
  - [x] Test: recipe card renders image container and recipe name when result provided — mock `_performSearch` or use the widget directly
  - [x] Follow the pattern from `app/test/recipe_books_test.dart` (StatefulWidget test with mock state)

## Dev Notes

### Current State — Read This Before Touching Anything

**The search infrastructure already exists end-to-end.** This story is a focused enhancement, NOT a greenfield build. Before writing any code, read:
- `services/api/src/api/v1/search/unified_search.py` — the actual backend (READ FIRST)
- `app/lib/features/search/search_screen.dart` — the actual frontend (READ FIRST)

**What exists today (do not rewrite these):**
- `GET /v1/search?q=...` — unified search endpoint, returns `{my_recipes, public_recipes, users}`
- `_recipe_matches()` in `UnifiedSearch` — OR condition matching name + description + ingredient
- `SearchScreen` — full working screen with debounce, error state, empty state, no-results state, section headers
- `ApiClient.search(String query)` at `app/lib/core/services/api_client.dart:241` — HTTP client method
- Route `/search` registered in `app/lib/core/router/app_router.dart`

**What's missing (only these two things):**
1. Tag matching in `_recipe_matches()` — `Recipe.tags` is `ARRAY(String)` but not searched
2. Photo-dominant card UI — `_buildRecipeTile()` uses 48×48 `ListTile` thumbnail

### Recipe Model — Tags Field

File: `libraries/utils/utils/models/recipe.py:35`

```python
tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True, default=list)
```

Tags are stored as a PostgreSQL `ARRAY(String)`. Examples: `['italian', 'dinner', 'quick']`.

### Adding Tag Search — Exact Code Pattern

Current `_recipe_matches()` (lines 46-61 in `unified_search.py`):
```python
from sqlalchemy import exists, or_, select  # CURRENT

def _recipe_matches(self, query: str):
    ingredient_match = exists(...)
    return or_(
        Recipe.name.ilike(f"%{query}%"),
        Recipe.description.ilike(f"%{query}%"),
        ingredient_match,
    )
```

Updated imports and method:
```python
from sqlalchemy import exists, func, or_, select  # ADD func

def _recipe_matches(self, query: str):
    ingredient_match = exists(
        select(RecipeIngredient.recipe_id)
        .join(Ingredient, RecipeIngredient.ingredient_id == Ingredient.id)
        .where(
            RecipeIngredient.recipe_id == Recipe.id,
            Ingredient.canonical_name.ilike(f"%{query}%"),
        )
    )

    # array_to_string converts ['italian','dinner'] to 'italian,dinner'
    # NULL tags → NULL ilike → NULL (not True) → no false positives
    tag_match = func.array_to_string(Recipe.tags, ',').ilike(f"%{query}%")

    return or_(
        Recipe.name.ilike(f"%{query}%"),
        Recipe.description.ilike(f"%{query}%"),
        ingredient_match,
        tag_match,
    )
```

### Frontend Card Design

**Current (to keep pattern, upgrade layout):**
```dart
// CURRENT — 48×48 thumbnail in ListTile
Widget _buildRecipeTile(dynamic recipe, {required bool isPublic}) {
  return ListTile(
    leading: recipe['image_url'] != null
        ? ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: Image.network(recipe['image_url'], width: 48, height: 48, ...),
          )
        : _buildRecipeIcon(),   // 48×48 fallback
    ...
  );
}
```

**New — Photo-dominant card (replace ListTile with Card):**
Use a `Card` with a taller image area (~120px) on the left, recipe info on the right. Or a full-width image at top of card with text below. Match whatever `RecipeListTile` / recipe cards look like elsewhere in the app (check `app/lib/features/recipes/` for consistent card patterns). Do NOT use AppColors — continue using `colorScheme.*` from `Theme.of(context).colorScheme`.

The key requirement: image must be visually dominant (not a 48px icon-sized thumbnail).

### Search Endpoint Pattern (Architecture Mandate)

All API operations MUST use the `Endpoint` base class pattern:
```python
class MyEndpoint(Endpoint):
    def execute(self, param: str):
        return success(data=...)
```

`unified_search.py` already follows this. Do NOT break this pattern.

### SQLAlchemy `func` Usage

`func` from SQLAlchemy maps to PostgreSQL SQL functions. `func.array_to_string(col, sep)` generates:
```sql
array_to_string(recipes.tags, ',')
```

This is safe to call on a nullable ARRAY column — PostgreSQL returns NULL, and `NULL ILIKE '%query%'` evaluates to NULL (falsy), so no false positives.

### API Response Format — `my_recipes` vs `public_recipes`

The search response splits into:
- `my_recipes`: recipes from books where `RecipeBookUser.user_id = current_user.id` (personal + shared books the user joined)
- `public_recipes`: recipes from public books the user is NOT a member of

Both sections go through `_recipe_matches()`, so adding tag match to that method covers both sections automatically.

### Performance Requirement (AC #3)

P95 < 2 seconds. The existing query uses:
- `ILIKE '%query%'` — full table scan; acceptable at current scale (< 1000 recipes per user)
- `EXISTS` subquery for ingredients — correlated but bounded by user's books filter
- Adding `array_to_string(...).ilike(...)` has similar cost to description ilike

No additional indexing needed for Story 5.1. Story 5.2 introduces pg_trgm GIN index and pgvector for semantic search.

### What NOT To Do

- Do NOT implement fuzzy/typo-tolerant search (that's Story 5.2 — pg_trgm + pgvector)
- Do NOT implement filter chips/facets (that's Story 5.3)
- Do NOT implement contextual home screen (that's Story 5.4)
- Do NOT rewrite the entire SearchScreen — it already works, just enhance `_buildRecipeTile()`
- Do NOT change the API endpoint signature, response shape, or minimum query length
- Do NOT add a new endpoint — the existing `/v1/search` is sufficient
- Do NOT switch frontend theming from `colorScheme.*` to `AppColors` — search screen is not in cook mode

### References

- [Source: services/api/src/api/v1/search/unified_search.py] — existing backend implementation to enhance
- [Source: app/lib/features/search/search_screen.dart] — existing frontend to enhance
- [Source: libraries/utils/utils/models/recipe.py:35] — `Recipe.tags` ARRAY(String) field
- [Source: app/lib/core/services/api_client.dart:241] — `search()` method, no changes needed
- [Source: app/lib/core/router/app_router.dart] — `/search` route, no changes needed
- [Source: services/api/tests/test_search.py] — existing test file to add tag test to
- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.1] — story requirements
- [Source: _bmad-output/planning-artifacts/architecture.md] — `Endpoint` pattern mandate, SQLAlchemy 2.0 async ORM, PostgreSQL 16 + pgvector + pg_trgm stack

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

### Completion Notes List

- Tag matching added via `func.array_to_string(Recipe.tags, ",").ilike(...)` — handles NULL tags safely (NULL ILIKE = NULL, not True)
- Photo-dominant card replaced 48×48 `ListTile` with 100×100 `Card` layout
- Backend test `test_search_by_tag` verifies response shape (not end-to-end SQL due to mock abstraction)
- Response body is the serialized Pydantic model directly (no `data` wrapper key) — `handle_result` calls `jsonable_encoder(result['data'])`
- Code Review (M1 FIXED): Improved `test_search_by_tag` to reset mock and assert `execute.call_count >= 1` — proves DB query logic ran
- Code Review (M2 DOCUMENTED): Flutter tests test standalone widget primitives — DI harness required for actual SearchScreen; comment added
- Code Review (L1 FIXED): Added `loadingBuilder` to `Image.network` in `_buildRecipeTile()` — shows icon placeholder while loading
- Code Review (L2 NOTE): Test file at `app/test/` root (consistent with other existing tests, architecture convention not enforced project-wide)
- Code Review (L3 NOTE): Pre-existing N+1 on `recipe.ingredients[:5]` — deferred to Story 5.2 which introduces joinedload + pg_trgm

### File List

- `services/api/src/api/v1/search/unified_search.py` — added `func` import + `tag_match` to `_recipe_matches()`
- `app/lib/features/search/search_screen.dart` — replaced `_buildRecipeTile()` with photo-dominant Card layout
- `services/api/tests/test_search.py` — added `test_search_by_tag()`
- `app/test/search_screen_test.dart` — created with 2 widget tests
