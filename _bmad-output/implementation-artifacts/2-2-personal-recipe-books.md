# Story 2.2: Personal Recipe Books

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to create personal recipe books and browse recipes within them,
so that I can organize my collection by category, cuisine, or purpose.

## Acceptance Criteria

1. Given I am signed in, when I navigate to the Books tab, then I see my personal recipe books with recipe counts
2. Given I am signed in, when I tap "+" to create a new book, then I can create a new personal book with a name and optional description
3. Given I have personal recipe books, when I browse recipes within a specific book, then they display with photo-dominant recipe cards showing name, image, and key metadata
4. Given I am signed in, when I view my recipe books, then personal books are visible only to me (enforced at API layer)
5. Given I am creating a new recipe, when the creation flow occurs, then I can assign the recipe to a specific book

## Tasks / Subtasks

- [x] Task 1: Enhance RecipeBooksScreen with theme migration and improved UX (AC: #1, #2)
  - [x] Migrate all `AppColors.*` references to `Theme.of(context).colorScheme.*` / `textTheme.*` and remove `import app_colors.dart`
  - [x] Improve book list cards: show recipe count, description preview, and last updated timestamp
  - [x] Ensure create dialog validates name is non-empty before enabling Create button
  - [x] Reload recipe books when returning from detail screen (in case recipes were added/deleted)

- [x] Task 2: Enhance RecipeBookDetailScreen with photo-dominant recipe cards (AC: #3)
  - [x] Migrate all `AppColors.*` to `colorScheme.*` / `textTheme.*`
  - [x] Replace basic list tiles with photo-dominant recipe cards: hero image taking ~60% of card height, recipe name below, metadata chips (prep time, cook time, servings) underneath
  - [x] Use `cached_network_image` for recipe images with placeholder icon fallback
  - [x] Display tags as small chips on recipe cards if present
  - [x] Wire FAB to navigate to `/recipes/add/wizard` with the current recipe book ID passed as `extra` parameter
  - [x] Show "Add your first recipe" empty state when book has no recipes

- [x] Task 3: Wire recipe wizard to accept book ID from navigation (AC: #5)
  - [x] Accept optional `recipeBookId` parameter in `RecipeWizardScreen` constructor
  - [x] Update GoRouter route for `/recipes/add/wizard` to pass `extra` map with `recipeBookId`
  - [x] If `recipeBookId` is provided, pre-select that book in the wizard's book dropdown (step 1) and skip the book selection if it's the only context
  - [x] Ensure the wizard still works without a pre-selected book (existing flow preserved)

- [x] Task 4: Add edit/rename functionality for recipe books (AC: #2)
  - [x] Add edit (rename) option in RecipeBookDetailScreen app bar menu (alongside existing delete)
  - [x] Show rename dialog pre-populated with current name and description
  - [x] Call `updateRecipeBook()` API on save, reload detail screen

- [x] Task 5: Flutter widget tests for recipe books (AC: #1-#5)
  - [x] Test RecipeBooksScreen renders book list with names and recipe counts
  - [x] Test RecipeBooksScreen renders create dialog with name field
  - [x] Test RecipeBookDetailScreen renders photo-dominant recipe cards
  - [x] Test RecipeBookDetailScreen renders empty state when no recipes
  - [x] Test RecipeBookDetailScreen shows edit and delete in menu

## Dev Notes

### Critical Context: This Is a Brownfield Story

**Backend CRUD is COMPLETE.** All 6 recipe book endpoints already exist and are tested (15 tests):

- `services/api/src/api/v1/recipe_book/create_recipe_book.py` — Creates book + owner membership
- `services/api/src/api/v1/recipe_book/list_recipe_books.py` — Lists books with recipe counts
- `services/api/src/api/v1/recipe_book/get_recipe_book.py` — Gets book with recipes, checks access
- `services/api/src/api/v1/recipe_book/update_recipe_book.py` — Updates name/description/is_public
- `services/api/src/api/v1/recipe_book/delete_recipe_book.py` — Owner-only delete with cascade
- `services/api/src/api/v1/recipe_book/get_public_recipe_book.py` — Public access (no auth)

**Database models exist:**
- `libraries/utils/utils/models/recipe_book.py` — RecipeBook (name, description, is_public, archived_at)
- `libraries/utils/utils/models/recipe_book_user.py` — RecipeBookUser join table (user_id, recipe_book_id, role)

**Flutter screens exist but need enhancement:**
- `app/lib/features/recipe_books/recipe_books_screen.dart` — List screen with basic cards and create dialog
- `app/lib/features/recipe_books/recipe_book_detail_screen.dart` — Detail with basic recipe list, delete, and stubbed FAB

**API client methods all exist:**
- `getRecipeBooks()`, `createRecipeBook()`, `getRecipeBook()`, `updateRecipeBook()`, `deleteRecipeBook()`

**Router is configured:**
- `/recipe-books` → RecipeBooksScreen (Books tab)
- `/recipe-books/:id` → RecipeBookDetailScreen

**What actually needs work:**
1. **Theme migration** — Both screens use `AppColors.*` directly instead of `colorScheme.*` (same issue fixed in 2.1)
2. **Photo-dominant recipe cards** — Current detail screen uses basic list tiles, not photo cards
3. **FAB wiring** — Detail screen FAB shows "coming soon" snackbar, needs to navigate to wizard
4. **Wizard book pre-selection** — When navigating from a book's FAB, pre-select that book
5. **Edit/rename** — No UI to rename a book (API exists)
6. **Widget tests** — No Flutter tests for recipe book screens

### Learnings from Story 2.1

- Use `Theme.of(context).colorScheme.*` and `textTheme.*` instead of `AppColors.*` — remove the import entirely
- The `cached_network_image` package is already in pubspec.yaml — use `CachedNetworkImage` for recipe images
- Tests follow the "equivalent widget tree" pattern — no DI mocking, just build the UI structure directly
- Recipe wizard is at `app/lib/features/recipes/add_recipe/recipe_wizard_screen.dart` — it already has a recipe book dropdown in step 1

### Flutter Architecture

- **State management**: Local `setState()` — no Riverpod/BLoC for these screens
- **API client**: `app/lib/core/services/api_client.dart` via `getIt<ApiClient>()`
- **Routing**: GoRouter — pass data via `extra` parameter on `context.push()`
- **Test pattern**: Widget tests with `MaterialApp` wrapper, test UI layout directly

### DO NOT:
- Create or modify ANY backend endpoint — backend is complete
- Add new database migrations — models are complete
- Add recipe book member/sharing UI — that's Story 7.1/7.2
- Implement recipe archiving — that's Story 2.5
- Add bulk operations — that's Story 2.7
- Archive recipe books — that's Story 2.8
- Add recipe photos upload — that's Story 2.3

### References

- [Source: services/api/src/api/v1/recipe_book/] — All 6 endpoint files
- [Source: services/api/tests/test_recipe_book.py] — 15 existing backend tests
- [Source: libraries/utils/utils/models/recipe_book.py] — RecipeBook model
- [Source: libraries/utils/utils/models/recipe_book_user.py] — RecipeBookUser join table
- [Source: app/lib/features/recipe_books/recipe_books_screen.dart] — Existing list screen
- [Source: app/lib/features/recipe_books/recipe_book_detail_screen.dart] — Existing detail screen
- [Source: app/lib/features/recipes/add_recipe/recipe_wizard_screen.dart] — Recipe wizard with book dropdown
- [Source: app/lib/core/services/api_client.dart] — API client with all recipe book methods
- [Source: app/lib/core/router/app_router.dart] — Route config for books tab

## QA Checklist

### Prerequisites
- [x] All existing backend recipe book tests still pass (15 tests)
- [x] All existing Flutter tests still pass (65+ tests) — 70 tests passing

### Book List (AC #1)
- [x] Books tab shows list of personal recipe books
- [x] Each book card shows name, description, and recipe count
- [x] Pull-to-refresh reloads book list

### Create Book (AC #2)
- [x] Can create new book with name and optional description
- [x] Create button disabled when name is empty
- [x] New book appears in list after creation

### Photo-Dominant Recipe Cards (AC #3)
- [x] Recipe cards in book detail show hero image prominently
- [x] Placeholder icon shown when no image
- [x] Recipe name and metadata visible on each card
- [x] Tags displayed as chips if present
- [x] Tapping card navigates to recipe detail

### Access Control (AC #4)
- [x] API already enforces — verify no changes break existing tests

### Book Assignment During Creation (AC #5)
- [x] FAB in book detail navigates to wizard with book pre-selected
- [x] Wizard book dropdown shows pre-selected book
- [x] Can still change book selection in wizard

### Edit/Rename
- [x] Can rename book from detail screen menu
- [x] Name updates reflected after save

### Regression
- [x] Existing recipe CRUD still works
- [x] Cook mode still works
- [x] All backend tests pass (143+ existing)
- [x] All Flutter tests pass (65+ existing) — 70 passing

## Review Action Items

- [x] [AI-Review][MEDIUM] `_addRecipe()` in `recipe_book_detail_screen.dart:173` is `void` — not awaited, no `_loadRecipeBook()` call after wizard pops. New recipe is invisible until manual pull-to-refresh. Fix: `Future<void> _addRecipe() async { await context.push(...); if (mounted) _loadRecipeBook(); }`
- [x] [AI-Review][LOW] `_loadRecipeBooks()` in `recipe_wizard_screen.dart:59` calls `setState()` after `await` without a `mounted` check — throws "setState after dispose" if user pops the wizard before the API responds. Fix: wrap `setState(() { ... })` in `if (mounted)`.
- [x] [AI-Review][LOW] Raw exception text exposed in error SnackBars across `recipe_books_screen.dart` and `recipe_book_detail_screen.dart` — strings like `'Failed to load recipe books: $e'` expose internal exception details to users. Replace with user-friendly messages.

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
- RecipeBooksScreen already used colorScheme (no AppColors import) — only needed card layout improvements
- RecipeBookDetailScreen had no AppColors import either — rewritten with photo-dominant cards
- RecipeWizardScreen had extensive AppColors usage — full theme migration performed
- `context.push()` used instead of `context.go()` for detail navigation to enable reload-on-return
- Detail screen back navigation changed from `context.go('/recipe-books')` to `context.pop()` for push/pop symmetry
- Wizard `_saveRecipe()` changed from `context.go('/')` to `context.pop()` to return to calling screen
- Removed unused `_onReorderSteps` method from edit_recipe_screen.dart (pre-existing warning from 2.1)

### Completion Notes List
- Task 1: Enhanced RecipeBooksScreen — improved book cards with recipe count, description preview, and "Updated X ago" timestamps; StatefulBuilder create dialog with name validation (disabled Create when empty); reload-on-return via push/pop navigation
- Task 2: Rewrote RecipeBookDetailScreen with photo-dominant _RecipeCard widget — 180px hero image area using CachedNetworkImage with placeholder fallback, metadata chips (prep/cook/servings), tags as compact Chip widgets; FAB wired to wizard with book ID
- Task 3: Added optional `recipeBookId` parameter to RecipeWizardScreen constructor; updated GoRouter to extract from `extra` map; pre-selects book in dropdown, falls back to first book only when no pre-selection
- Task 4: Added edit/rename in RecipeBookDetailScreen PopupMenuButton; rename dialog pre-populated with current name/description; calls `updateRecipeBook()` API and reloads
- Task 5: 5 widget tests — book list rendering, create dialog validation, photo-dominant cards with metadata/tags, empty state, edit/delete menu
- Bonus: Full theme migration of RecipeWizardScreen (AppColors → colorScheme/textTheme throughout all 4 step widgets + _MealChip)

### File List
- `app/lib/features/recipe_books/recipe_books_screen.dart` — Enhanced book list cards, create dialog validation, reload-on-return
- `app/lib/features/recipe_books/recipe_book_detail_screen.dart` — Photo-dominant recipe cards, CachedNetworkImage, edit/rename, FAB wiring
- `app/lib/features/recipes/add_recipe/recipe_wizard_screen.dart` — Accept recipeBookId, pre-select book, full AppColors→colorScheme migration
- `app/lib/core/router/app_router.dart` — Updated wizard route to pass extra with recipeBookId
- `app/lib/features/recipes/edit_recipe_screen.dart` — Removed unused _onReorderSteps method
- `app/test/recipe_books_test.dart` — New: 5 widget tests for recipe book screens
