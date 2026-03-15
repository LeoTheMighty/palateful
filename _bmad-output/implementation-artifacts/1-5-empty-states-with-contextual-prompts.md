# Story 1.5: Empty States with Contextual Prompts

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to see helpful guidance when sections are empty,
so that I know what to do next instead of staring at a blank screen.

## Acceptance Criteria

1. Given I have no recipes, books, shopping items, or planned meals, when I navigate to any empty section, then I see a contextual prompt (e.g., empty book -> "Add your first recipe", empty cart -> "Plan a meal to get started")
2. And the prompt includes an actionable button that takes me to the relevant creation flow
3. And the empty state disappears once content is added
4. And empty states use warm, encouraging tone consistent with the design system

## Tasks / Subtasks

- [x] Task 1: Create shared `EmptyStateWidget` (AC: #1, #2, #4)
  - [x] Create `app/lib/shared/widgets/empty_state.dart` with reusable `EmptyStateWidget`
  - [x] Parameters: `icon`, `title`, `subtitle`, optional `actionLabel` + `onAction` + `actionIcon`
  - [x] Theme-aware: all colors from `colorScheme.*` and `textTheme.*`
  - [x] Match home screen's existing empty state pattern (icon in rounded container, title, subtitle, CTA button)
  - [x] Export from `app/lib/shared/widgets/widgets.dart`

- [x] Task 2: Migrate Home Screen to shared widget (AC: #1, #2, #3)
  - [x] Replace `_buildEmptyState()` body with `EmptyStateWidget(icon: Icons.restaurant_menu, title: 'No recipes yet', subtitle: 'Add your first recipe to get started', actionLabel: 'Add Recipe', onAction: _showAddRecipeSheet, actionIcon: Icons.add)`
  - [x] Home screen already uses `colorScheme.*` — no other migrations needed

- [x] Task 3: Theme-migrate Recipe Books Screen + add CTA (AC: #1, #2, #4)
  - [x] Replace inline empty state (lines 159-197) with `EmptyStateWidget(icon: Icons.book_outlined, title: 'No recipe books yet', subtitle: 'Create your first book to organize your collection', actionLabel: 'Create Recipe Book', onAction: _createRecipeBook, actionIcon: Icons.add)`
  - [x] Replace error state `AppColors.errorLight`/`AppColors.errorDark` with `colorScheme.errorContainer`/`colorScheme.onErrorContainer`
  - [x] Replace list item colors: `AppColors.beige` -> `colorScheme.primaryContainer`, `AppColors.textSecondary` -> `colorScheme.onSurfaceVariant`, `AppColors.textTertiary` -> `colorScheme.outline`
  - [x] Remove `import '../../core/theme/app_colors.dart';`

- [x] Task 4: Theme-migrate Recipe Book Detail Screen + add CTA (AC: #1, #2, #4)
  - [x] Replace inline empty state (lines 193-228) with `EmptyStateWidget(icon: Icons.restaurant_menu, title: 'No recipes yet', subtitle: 'Add your first recipe to this book', actionLabel: 'Add Recipe', actionIcon: Icons.add)` — CTA can show snackbar for now since add-recipe-to-book is not yet wired
  - [x] Replace error state `AppColors.errorLight`/`AppColors.errorDark` -> `colorScheme.errorContainer`/`colorScheme.onErrorContainer`
  - [x] Replace delete button `AppColors.error`/`AppColors.cream` -> `colorScheme.error`/`colorScheme.onError`
  - [x] Replace description text `AppColors.textSecondary` -> `colorScheme.onSurfaceVariant`
  - [x] Replace list item colors: `AppColors.beige` -> `colorScheme.primaryContainer`, `AppColors.textSecondary` -> `colorScheme.onSurfaceVariant`, `AppColors.textTertiary` -> `colorScheme.outline`
  - [x] Remove `import '../../core/theme/app_colors.dart';`

- [x] Task 5: Theme-migrate Search Screen empty states (AC: #1, #4)
  - [x] Replace `Scaffold(backgroundColor: AppColors.cream)` -> remove explicit background (use theme default)
  - [x] Replace `AppBar(backgroundColor: AppColors.cream)` -> remove explicit background (use theme default)
  - [x] Replace pre-search state `AppColors.textTertiary` -> `colorScheme.onSurfaceVariant`
  - [x] Replace no-results state `AppColors.textTertiary`/`AppColors.textSecondary` -> `colorScheme.outline`/`colorScheme.onSurfaceVariant`
  - [x] Replace error state `AppColors.textSecondary` -> `colorScheme.onSurfaceVariant`
  - [x] Replace hint style `AppColors.textTertiary` -> `colorScheme.onSurfaceVariant`
  - [x] Replace section header `AppColors.textTertiary` -> `colorScheme.outline`
  - [x] Replace recipe tile colors: `AppColors.textTertiary` -> `colorScheme.outline`, `AppColors.beige` -> `colorScheme.primaryContainer`, `AppColors.textSecondary` -> `colorScheme.onSurfaceVariant`
  - [x] Replace user tile colors: same pattern
  - [x] Remove `import '../../core/theme/app_colors.dart';`

- [x] Task 6: Upgrade Cart + Calendar placeholder screens (AC: #1, #4)
  - [x] Cart: Replace current placeholder with themed `EmptyStateWidget(icon: Icons.shopping_cart_outlined, title: 'No shopping lists yet', subtitle: 'Plan a meal and add ingredients to get started')`
  - [x] Calendar: Replace current placeholder with themed `EmptyStateWidget(icon: Icons.calendar_today_outlined, title: 'No meals planned yet', subtitle: 'Your weekly meal plan will appear here')`
  - [x] Both: Use `colorScheme.*` for AppBar (remove explicit colors or use theme defaults)
  - [x] No CTA buttons for these yet — features are not implemented

- [x] Task 7: Write widget tests (AC: #1-4)
  - [x] Test `EmptyStateWidget` renders icon, title, subtitle
  - [x] Test `EmptyStateWidget` renders CTA button when provided
  - [x] Test `EmptyStateWidget` hides CTA button when not provided
  - [x] Test CTA button triggers callback
  - [x] Test empty states in key screens: recipe books, cart, calendar (use equivalent widget trees like Stories 1.3/1.4)
  - [x] `GoogleFonts.config.allowRuntimeFetching = false` in `setUp()` if any test uses GoogleFonts
  - [x] Run all existing tests: `cd app && flutter test` — no regressions

## Dev Notes

### Critical Context: This Is a Brownfield Project

**Empty states already exist in most screens.** The existing codebase has:
- `HomeScreen._buildEmptyState()` at `home_screen.dart:344-389` — **already theme-aware** with `colorScheme.*`. This is the gold-standard pattern to replicate.
- `RecipeBooksScreen` at `recipe_books_screen.dart:159-197` — inline empty state using `AppColors.*` (beige, textPrimary, textSecondary, textTertiary). No CTA button.
- `RecipeBookDetailScreen` at `recipe_book_detail_screen.dart:193-228` — inline empty state using `AppColors.*`. No CTA button.
- `SearchScreen` at `search_screen.dart:133-161` — two states using `AppColors.*`: pre-search and no-results.
- `CartScreen` at `cart_screen.dart` — bare placeholder: icon + "Shopping list coming soon". No theming.
- `CalendarScreen` at `calendar_screen.dart` — bare placeholder: icon + "Meal planning coming soon". No theming.
- `ShoppingListScreen` at `shopping_list_screen.dart:373-402` — empty state using `AppColors.*`. **DO NOT touch this file** — it's a complex screen with extensive `AppColors` usage throughout (50+ references). That migration belongs in Epic 8 when the shopping list feature is properly built.

**What ACTUALLY needs to be done:**
1. Create a shared `EmptyStateWidget` modeled on the home screen pattern
2. Replace all inline empty states with the shared widget
3. Theme-migrate `AppColors.*` -> `colorScheme.*` in affected files
4. Add contextual CTA buttons where missing
5. Upgrade cart/calendar placeholders to proper themed empty states
6. Write widget tests

**DO NOT:**
- Touch `shopping_list_screen.dart` — out of scope, too many `AppColors` references
- Touch `home_screen.dart` beyond swapping to `EmptyStateWidget` — already theme-compliant
- Create any backend endpoints — this is frontend-only
- Add new routes or screens

### AppColors -> Theme Mapping Reference

```
AppColors.beige         -> colorScheme.primaryContainer
AppColors.cream         -> (remove explicit, use theme default scaffold background)
AppColors.textPrimary   -> colorScheme.onSurface
AppColors.textSecondary -> colorScheme.onSurfaceVariant
AppColors.textTertiary  -> colorScheme.outline
AppColors.textDisabled  -> colorScheme.outline (with opacity if needed)
AppColors.errorLight    -> colorScheme.errorContainer
AppColors.errorDark     -> colorScheme.onErrorContainer
AppColors.error         -> colorScheme.error
AppColors.chocolate     -> colorScheme.primary
```

### EmptyStateWidget Design Spec

Based on the gold-standard `home_screen.dart:344-389`:
```
[Rounded container with surfaceContainerHighest background]
  [Icon, size 56, onSurfaceVariant color]
[24px gap]
[Title: titleLarge, w600, onSurface]
[8px gap]
[Subtitle: bodyMedium, onSurfaceVariant, center-aligned]
[24px gap — only if CTA present]
[ElevatedButton.icon — only if actionLabel provided]
```

Widget is wrapped in `Center > Padding(32) > Column(mainAxisAlignment: center)`.

### Contextual Copy

| Screen | Title | Subtitle | CTA |
|--------|-------|----------|-----|
| Home (no recipes) | No recipes yet | Add your first recipe to get started | Add Recipe |
| Recipe Books (no books) | No recipe books yet | Create your first book to organize your collection | Create Recipe Book |
| Recipe Book Detail (empty book) | No recipes yet | Add your first recipe to this book | Add Recipe |
| Search (pre-search) | Search your recipes | Find recipes by name, ingredient, or tag | (none) |
| Search (no results) | No results for "{query}" | Try a different search term | (none) |
| Cart (placeholder) | No shopping lists yet | Plan a meal and add ingredients to get started | (none) |
| Calendar (placeholder) | No meals planned yet | Your weekly meal plan will appear here | (none) |

### File Structure

**Files to CREATE:**
- `app/lib/shared/widgets/empty_state.dart` — shared `EmptyStateWidget`
- `app/test/empty_state_test.dart` — widget tests

**Files to MODIFY:**
- `app/lib/shared/widgets/widgets.dart` — add export for `empty_state.dart`
- `app/lib/features/home/home_screen.dart` — swap to `EmptyStateWidget`
- `app/lib/features/recipe_books/recipe_books_screen.dart` — full `AppColors` migration + `EmptyStateWidget`
- `app/lib/features/recipe_books/recipe_book_detail_screen.dart` — full `AppColors` migration + `EmptyStateWidget`
- `app/lib/features/search/search_screen.dart` — full `AppColors` migration
- `app/lib/features/cart/cart_screen.dart` — themed empty state
- `app/lib/features/calendar/calendar_screen.dart` — themed empty state

**Files to NOT TOUCH:**
- `app/lib/features/shopping_cart/` — entire directory is out of scope (Epic 8)
- `app/lib/core/theme/app_colors.dart` — still used by other un-migrated screens
- `app/lib/core/theme/theme.dart` — theme already set up correctly
- `app/lib/core/router/app_router.dart` — routing works as-is
- `app/lib/shared/widgets/buttons.dart` — button components work as-is
- Any backend files — no backend changes needed

### Testing Requirements

- Widget test: `EmptyStateWidget` renders icon, title, subtitle correctly
- Widget test: `EmptyStateWidget` shows/hides CTA button based on props
- Widget test: CTA button fires callback when tapped
- Widget test: Recipe books screen empty state with CTA
- Widget test: Cart placeholder screen renders themed empty state
- Widget test: Calendar placeholder screen renders themed empty state
- Run existing tests: `cd app && flutter test` — no regressions (currently 44 passing)

### Library/Framework Requirements

No new libraries needed. All dependencies already installed.

### Previous Story Intelligence (Story 1.4)

From Story 1.4 implementation:
- **`mounted` checks**: Always add `if (!mounted) return;` after any async call before `setState` or `context.go()`. Already present in most screens — verify when touching files.
- **Widget tests without DI**: Cannot instantiate screens that depend on `getIt<AuthService>()` in tests. Test UI patterns directly with equivalent widget trees.
- **`GoogleFonts.config.allowRuntimeFetching = false`** needed in test `setUp()`.
- **Theme compliance**: All colors via `Theme.of(context).colorScheme.*`, headings via `GoogleFonts.playfairDisplay`.
- **Error container pattern**: `Container(decoration: BoxDecoration(color: colorScheme.errorContainer, borderRadius: BorderRadius.circular(12)), child: Text(error, style: TextStyle(color: colorScheme.onErrorContainer)))`.
- **`AppColors` removal**: When all references in a file are migrated, remove the `import '../../core/theme/app_colors.dart';` line entirely.
- **Don't over-scope**: Only migrate `AppColors` in files you're already touching for the story. Don't go hunting for other files.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.5] — User story and acceptance criteria
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md] — "Empty states with contextual prompts (empty book -> Add your first recipe)"
- [Source: _bmad-output/planning-artifacts/architecture.md#Anti-Patterns to Avoid] — No hardcoded colors, use theme system
- [Source: app/lib/features/home/home_screen.dart:344-389] — Gold-standard empty state pattern (already theme-aware)
- [Source: app/lib/features/recipe_books/recipe_books_screen.dart:159-197] — Empty state needing migration
- [Source: app/lib/features/recipe_books/recipe_book_detail_screen.dart:193-228] — Empty state needing migration
- [Source: app/lib/features/search/search_screen.dart:133-161] — Empty states needing migration
- [Source: app/lib/features/cart/cart_screen.dart] — Placeholder needing upgrade
- [Source: app/lib/features/calendar/calendar_screen.dart] — Placeholder needing upgrade
- [Source: app/lib/core/theme/app_colors.dart] — Full color mapping reference
- [Source: _bmad-output/implementation-artifacts/1-4-onboarding-flow.md] — Previous story learnings

## QA Checklist

### Prerequisites
- [ ] Run `cd app && flutter pub get`
- [ ] Run `cd app && flutter test` — all tests should pass
- [ ] Backend running (`docker compose up`)

### Shared EmptyStateWidget (AC #1, #4)
- [ ] Widget renders icon in rounded container
- [ ] Widget renders title and subtitle with theme-aware colors
- [ ] Widget shows CTA button when actionLabel provided
- [ ] Widget hides CTA button when actionLabel not provided
- [ ] Widget works in both light and dark mode

### Home Screen (AC #1, #2, #3)
- [ ] Empty state shows "No recipes yet" with CTA "Add Recipe"
- [ ] Tapping "Add Recipe" opens the add recipe sheet
- [ ] Empty state disappears when recipes are loaded
- [ ] No visual regression from current implementation

### Recipe Books Screen (AC #1, #2, #4)
- [ ] Empty state shows "No recipe books yet" with CTA "Create Recipe Book"
- [ ] Tapping CTA opens create recipe book dialog
- [ ] All colors are theme-aware (no AppColors references)
- [ ] Error state uses `colorScheme.errorContainer`
- [ ] List items use theme-aware colors

### Recipe Book Detail Screen (AC #1, #2, #4)
- [ ] Empty book shows "No recipes yet" with CTA
- [ ] All colors are theme-aware
- [ ] Error state uses `colorScheme.errorContainer`
- [ ] Delete button uses `colorScheme.error`

### Search Screen (AC #1, #4)
- [ ] Pre-search state themed ("Search your recipes")
- [ ] No-results state themed with icon
- [ ] All colors are theme-aware
- [ ] No AppColors references remain

### Cart + Calendar Placeholders (AC #1, #4)
- [ ] Cart shows themed empty state with warm message
- [ ] Calendar shows themed empty state with warm message
- [ ] Both use `colorScheme.*` colors
- [ ] No plain "coming soon" text — use warm, encouraging tone

### Design System (AC #4)
- [ ] All empty states use consistent visual pattern (icon + title + subtitle)
- [ ] All colors from theme (no AppColors in modified files)
- [ ] Warm, encouraging copy in all empty states
- [ ] Consistent with home screen, onboarding, and profile screen styling
- [ ] Works in dark mode

### Regression
- [ ] All existing Flutter tests pass
- [ ] Login flow unaffected
- [ ] Profile screen unaffected
- [ ] Onboarding flow unaffected
- [ ] Bottom nav tabs still work

## Review Action Items

- [x] [AI-Review][MEDIUM] `recipe_book_detail_screen.dart:218`: Added `errorBuilder` to `Image.network` for recipe thumbnails — failed image loads now show the same `Container + Icons.restaurant` fallback as the null-URL path.
- [x] [AI-Review][LOW] `empty_state.dart:66`: Added `assert(actionLabel == null || onAction != null, 'onAction must be provided when actionLabel is set')` to constructor.
- [x] [AI-Review][LOW] `recipe_books_screen.dart:51`: Wrapped `_createRecipeBook()` in try/finally to guarantee `nameController.dispose()` and `descriptionController.dispose()` on all paths.
- [x] [AI-Review][LOW] `search_screen.dart:137`: Updated pre-search state to title: "Search your recipes", subtitle: "Find recipes by name, ingredient, or tag" per spec.
- [x] [AI-Review][LOW] `empty_state.dart:68`: Replaced manual `ElevatedButton(Row([Icon, SizedBox, Text]))` with `ElevatedButton.icon` for M3-correct spacing. Updated test to use `find.byWidgetPredicate` since `.icon` factory creates internal `_ElevatedButtonWithIcon`.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

### Completion Notes List

- Task 1: Created `EmptyStateWidget` in `app/lib/shared/widgets/empty_state.dart`. Reusable widget with icon in rounded container, title, subtitle, and optional CTA button. All colors via `colorScheme.*` and `textTheme.*`. Exported from `widgets.dart`.
- Task 2: Replaced `HomeScreen._buildEmptyState()` inline code with `EmptyStateWidget` call. Added import. No other changes needed — home screen was already theme-compliant.
- Task 3: Full `AppColors` migration of `recipe_books_screen.dart`. Replaced inline empty state with `EmptyStateWidget` including "Create Recipe Book" CTA. Migrated error state to `colorScheme.errorContainer`. Migrated list item colors (beige→primaryContainer, textSecondary→onSurfaceVariant, textTertiary→outline). Removed `app_colors.dart` import.
- Task 4: Full `AppColors` migration of `recipe_book_detail_screen.dart`. Replaced inline empty state with `EmptyStateWidget` including "Add Recipe" CTA (shows snackbar since add-to-book not wired). Migrated error state, delete button colors, description text, and all list item colors. Removed `app_colors.dart` import.
- Task 5: Full `AppColors` migration of `search_screen.dart`. Removed explicit `backgroundColor` from Scaffold and AppBar (using theme defaults). Migrated pre-search, no-results, error states. Migrated hint style, section headers, recipe tile colors, user tile colors, recipe icon, and user avatar. Removed `app_colors.dart` import.
- Task 6: Upgraded `cart_screen.dart` and `calendar_screen.dart` placeholders from bare "coming soon" text to themed `EmptyStateWidget` with warm, encouraging copy. No CTA buttons (features not implemented yet).
- Task 7: Created 8 widget tests covering EmptyStateWidget (icon/title/subtitle rendering, CTA show/hide, callback trigger, container decoration) and screen-specific empty states (recipe books, cart, calendar). All 52 Flutter tests pass (44 existing + 8 new). No regressions.

### File List

**Created:**
- `app/lib/shared/widgets/empty_state.dart` — shared `EmptyStateWidget`
- `app/test/empty_state_test.dart` — 8 widget tests

**Modified:**
- `app/lib/shared/widgets/widgets.dart` — added export for `empty_state.dart`
- `app/lib/features/home/home_screen.dart` — swapped inline empty state to `EmptyStateWidget`
- `app/lib/features/recipe_books/recipe_books_screen.dart` — full `AppColors` migration + `EmptyStateWidget` with CTA
- `app/lib/features/recipe_books/recipe_book_detail_screen.dart` — full `AppColors` migration + `EmptyStateWidget` with CTA
- `app/lib/features/search/search_screen.dart` — full `AppColors` migration
- `app/lib/features/cart/cart_screen.dart` — themed empty state replacing placeholder
- `app/lib/features/calendar/calendar_screen.dart` — themed empty state replacing placeholder
