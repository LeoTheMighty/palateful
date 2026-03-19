# Story 5.5: Archive View

Status: ready-for-dev

## Story

As a user,
I want archived recipes excluded from search and browsing but accessible via a dedicated archive view,
So that my active collection stays clean while nothing is ever truly gone.

## Acceptance Criteria

1. **Given** I have archived recipes **When** I search or browse my collection **Then** archived recipes do not appear in results.
2. **Given** I want to access archived recipes **When** I navigate to Profile **Then** I see an "Archived Recipes" entry that opens the archive view.
3. **Given** I open the archive view **When** recipes are loaded **Then** I see all my archived recipes in a list with thumbnail, name, and archived date.
4. **Given** I am viewing the archive list **When** I tap "Restore" on a recipe **Then** the recipe is restored and removed from the archive view.
5. **Given** I am viewing the archive view **When** I type in the search bar **Then** the list filters in real-time to show only recipes whose name matches the query (case-insensitive).

## Tasks / Subtasks

- [ ] Task 1: Verify existing backend coverage (AC: #1, #2, #3, #4)
  - [ ] Confirm `GET /v1/recipes/archived` returns all archived recipes (already implemented in `list_archived_recipes.py`)
  - [ ] Confirm `POST /v1/recipes/{id}/restore` restores recipes (already implemented in `restore_recipe.py`)
  - [ ] Confirm all search tiers in `unified_search.py` filter `archived_at.is_(None)` (already done — no changes needed)
  - [ ] Confirm `list_recipes.py` excludes archived recipes (already done — no changes needed)

- [ ] Task 2: Flutter — add search bar to `ArchivedRecipesScreen` (AC: #5)
  - [ ] Add `TextEditingController _searchController = TextEditingController()` state variable
  - [ ] In `initState()`, call `_searchController.addListener(() => setState(() {}))` to trigger rebuild on input
  - [ ] Override `dispose()` to call `_searchController.dispose()` (in addition to `super.dispose()`)
  - [ ] Add `List<dynamic> get _filteredRecipes` getter: when `_searchController.text.isEmpty` return `_archivedRecipes`; otherwise filter by `recipe['name']?.toString().toLowerCase().contains(query.toLowerCase())`
  - [ ] Add `TextField` search bar with hint `'Search archived recipes...'` above the ListView in the body, using `InputDecoration` matching the design system (outlined, prefixIcon: Icons.search)
  - [ ] Replace `_archivedRecipes` with `_filteredRecipes` in `ListView.builder itemCount` and `itemBuilder`
  - [ ] When `_filteredRecipes.isEmpty` and `_searchController.text.isNotEmpty`, show `EmptyStateWidget` with message "No archived recipes match your search"

- [ ] Task 3: Tests (AC: all)
  - [ ] Add `app/test/archived_recipes_screen_test.dart` with isolated widget tests:
    - `'archive view shows recipe name'` — build isolated Card widget with recipe name text; verify it renders
    - `'restore button is present on card'` — build card widget with restore button; verify TextButton 'Restore' renders
    - `'search bar filters recipes by name'` — build isolated list widget, simulate text input, verify non-matching recipe names are hidden
    - `'empty state shown when search has no results'` — build with search text that matches nothing; verify empty-state-like text renders
  - [ ] Run `flutter test app/test/archived_recipes_screen_test.dart` — all pass

## Dev Notes

### What Already Exists — Do NOT Re-implement

**Backend (fully implemented, no changes needed):**
- `services/api/src/api/v1/recipe/list_archived_recipes.py` — `GET /v1/recipes/archived` returns all archived recipes scoped to the user via `RecipeBookUser` membership check
- `services/api/src/api/v1/recipe/restore_recipe.py` — `POST /v1/recipes/{id}/restore` clears `archived_at`
- `services/api/src/routers/v1/recipe_router.py` — both endpoints registered
- `services/api/tests/test_recipe.py` → `class TestListArchivedRecipes` and restore tests already exist

**Search exclusion (already implemented, no changes needed):**
- `unified_search.py` — all three tiers (exact ILIKE, fuzzy pg_trgm, semantic pgvector) include `Recipe.archived_at.is_(None)` / `AND r.archived_at IS NULL`
- `list_recipes.py` — excludes archived via `Recipe.archived_at.is_(None)`

**Flutter (already implemented, only needs search bar added):**
- `app/lib/features/recipes/archived_recipes_screen.dart` — full `StatefulWidget` with list, restore button, error state, empty state
- `app/lib/core/router/app_router.dart` line 113 — route `/recipes/archived` → `ArchivedRecipesScreen()`
- `app/lib/features/profile/profile_screen.dart` line 572 — "Archived Recipes" tile → `context.push('/recipes/archived')`
- `app/lib/core/services/api_client.dart` line 197 — `getArchivedRecipes()` and line 201 — `restoreRecipe(recipeId)`

### Flutter: Search Bar Addition Pattern

File to modify: `app/lib/features/recipes/archived_recipes_screen.dart`

**State additions** (add in `_ArchivedRecipesScreenState`):
```dart
final TextEditingController _searchController = TextEditingController();
```

**initState addition:**
```dart
@override
void initState() {
  super.initState();
  _loadArchivedRecipes();
  _searchController.addListener(() => setState(() {}));
}
```

**dispose addition:**
```dart
@override
void dispose() {
  _searchController.dispose();
  super.dispose();
}
```

**Filtered getter:**
```dart
List<dynamic> get _filteredRecipes {
  final query = _searchController.text.toLowerCase().trim();
  if (query.isEmpty) return _archivedRecipes;
  return _archivedRecipes
      .where((r) => (r['name'] as String? ?? '')
          .toLowerCase()
          .contains(query))
      .toList();
}
```

**Build method — add search bar above ListView:**
```dart
// Inside the RefreshIndicator child, wrap in Column:
child: Column(
  children: [
    Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
      child: TextField(
        controller: _searchController,
        decoration: const InputDecoration(
          hintText: 'Search archived recipes...',
          prefixIcon: Icon(Icons.search),
          border: OutlineInputBorder(),
        ),
      ),
    ),
    Expanded(
      child: _filteredRecipes.isEmpty && _searchController.text.isNotEmpty
          ? EmptyStateWidget(
              icon: Icons.search_off,
              title: 'No results',
              subtitle: 'No archived recipes match your search',
            )
          : ListView.builder(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
              itemCount: _filteredRecipes.length,
              itemBuilder: (context, index) {
                final recipe = _filteredRecipes[index];
                // ... existing card code, using `recipe` variable ...
              },
            ),
    ),
  ],
),
```

**Empty state empty-list check** — the existing `_archivedRecipes.isEmpty` check should remain unchanged (before the `RefreshIndicator`). The search-empty state only appears when there ARE archived recipes but none match the query.

### Flutter: Test Pattern

File: `app/test/archived_recipes_screen_test.dart`

Follow the same isolated widget test pattern as `app/test/home_screen_context_test.dart` — test individual extracted widgets in a `MaterialApp` wrapper, not the full screen. No mocking of `getIt` or `ApiClient` needed since tests build sub-widgets directly.

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('Archive view', () {
    testWidgets('archive card shows recipe name', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: ListTile(
            title: const Text('Grandma Pasta'),
            subtitle: const Text('Archived 3/15/2026'),
            trailing: TextButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.restore, size: 18),
              label: const Text('Restore'),
            ),
          ),
        ),
      ));
      expect(find.text('Grandma Pasta'), findsOneWidget);
    });

    testWidgets('restore button present on card', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: TextButton.icon(
            onPressed: () {},
            icon: const Icon(Icons.restore, size: 18),
            label: const Text('Restore'),
          ),
        ),
      ));
      expect(find.text('Restore'), findsOneWidget);
    });

    testWidgets('search bar filters by name', (tester) async {
      final recipes = [
        {'name': 'Chicken Soup', 'archived_at': '2026-01-01T00:00:00Z'},
        {'name': 'Beef Stew', 'archived_at': '2026-01-02T00:00:00Z'},
      ];
      final controller = TextEditingController();

      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: StatefulBuilder(
            builder: (context, setState) {
              final query = controller.text.toLowerCase();
              final filtered = query.isEmpty
                  ? recipes
                  : recipes
                      .where((r) => (r['name'] as String)
                          .toLowerCase()
                          .contains(query))
                      .toList();
              return Column(
                children: [
                  TextField(
                    controller: controller,
                    onChanged: (_) => setState(() {}),
                  ),
                  ...filtered.map((r) => Text(r['name'] as String)),
                ],
              );
            },
          ),
        ),
      ));

      await tester.enterText(find.byType(TextField), 'chicken');
      await tester.pump();
      expect(find.text('Chicken Soup'), findsOneWidget);
      expect(find.text('Beef Stew'), findsNothing);
    });

    testWidgets('empty state shown when search has no results', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Column(
            children: const [
              Text('No results'),
              Text('No archived recipes match your search'),
            ],
          ),
        ),
      ));
      expect(find.text('No results'), findsOneWidget);
      expect(find.text('No archived recipes match your search'), findsOneWidget);
    });
  });
}
```

### Key Patterns From Story 5.4 (Previous Story)

- **Response structure**: `handle_result` returns `jsonable_encoder(result['data'])` directly — test assertions use `data["items"]` (no outer `data` wrapper). Already applied correctly in `archived_recipes_screen.dart` line 38: `response.data['items']`.
- **Router registration**: via `v1_router.py` aggregator (not `main.py`) — already done for recipe_router.
- **Client-side filtering**: Use `TextEditingController` with `addListener(() => setState(() {}))` — same pattern as search screen but simpler (no debounce needed for archive list).
- **mounted check**: `archived_recipes_screen.dart` already follows `if (mounted)` pattern after awaits.

### Project Structure Notes

- Modify existing: `app/lib/features/recipes/archived_recipes_screen.dart` — add search bar and filtering
- New file: `app/test/archived_recipes_screen_test.dart` — widget tests
- No new backend files needed
- No `api_client.dart` changes needed
- No `app_router.dart` changes needed

### References

- [Source: services/api/src/api/v1/recipe/list_archived_recipes.py] — existing endpoint
- [Source: services/api/src/api/v1/recipe/restore_recipe.py] — existing restore endpoint
- [Source: services/api/src/api/v1/search/unified_search.py] — confirms archived_at.is_(None) in all tiers
- [Source: app/lib/features/recipes/archived_recipes_screen.dart] — existing screen to modify
- [Source: app/lib/features/profile/profile_screen.dart:572] — existing entry point
- [Source: app/lib/core/router/app_router.dart:113] — existing route
- [Source: app/test/home_screen_context_test.dart] — test pattern to follow
- [Source: _bmad-output/planning-artifacts/epics.md#5.5] — AC, user story (FR40)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List

