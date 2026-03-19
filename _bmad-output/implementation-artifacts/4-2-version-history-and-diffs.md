# Story 4.2: Version History & Diffs

Status: done

## Story

As a user,
I want to view the full version history of any recipe with diffs between versions,
so that I can see exactly what changed and when.

## Acceptance Criteria

1. When I tap the "History" button on a recipe detail screen, I see a timeline of all versions with timestamps and a label of what changed (e.g., "Ingredients changed", "Name changed")
2. The version count is visible on the recipe detail screen as an unobtrusive badge/chip (e.g., "v3") that doubles as the tap target for opening the history screen
3. I can tap any version in the timeline to view a diff (what was added, removed, changed)
4. The diff clearly highlights ingredient changes (added/removed/quantity changed) and step changes (added/removed/reordered/text changed)
5. Name and instructions changes are also shown in the diff if they were version-triggering fields
6. If a recipe has only one version (or zero), the history button/badge is still shown but tapping shows a single entry (the current state)
7. The history screen is accessible to any user with read access to the recipe (not just owners)

## Tasks / Subtasks

- [x] Task 1: Add backend endpoint `GET /recipes/:id/versions/:version_id` (AC: #3, #4, #5)
  - [x] Create `services/api/src/api/v1/recipe/get_recipe_version.py`
  - [x] Endpoint returns full snapshot JSONB for a single version
  - [x] Access check: user must have membership in recipe's recipe book
  - [x] Response: `{ id, version_number, snapshot, changed_fields, created_at }`
  - [x] Register in `services/api/src/api/v1/recipe/__init__.py`
  - [x] Add route to `services/api/src/routers/v1/recipe_router.py` as `GET /recipes/{recipe_id}/versions/{version_id}`

- [x] Task 2: Add version badge to recipe detail screen (AC: #2)
  - [x] In `recipe_detail_screen.dart`, read `version_count` from `_recipe['version_count']`
  - [x] Show version chip/badge below the time/servings row when `version_count > 0`
  - [x] Badge text: "v{version_count}" — tap navigates to `/recipes/{id}/versions`
  - [x] Use `_InfoChip`-style container with `Icons.history` icon
  - [x] If `version_count == 0`, do NOT show the badge (recipe has never been versioned yet)

- [x] Task 3: Add `getRecipeVersion` to API client (AC: #3)
  - [x] In `app/lib/core/services/api_client.dart`, add `getRecipeVersion(recipeId, versionId)`

- [x] Task 4: Create `RecipeVersionHistoryScreen` (AC: #1, #6, #7)
  - [x] Create `app/lib/features/recipes/recipe_version_history_screen.dart`
  - [x] StatefulWidget with `recipeId` and `recipeName` constructor params
  - [x] Loads version list via `_apiClient.getRecipeVersions(recipeId)` in `initState`
  - [x] Shows timeline list with version number, timestamp, changed field chips
  - [x] Tap on any version row → navigate to `/recipes/{recipeId}/versions/{versionId}`
  - [x] Loading, error, and empty states
  - [x] Timeline visual with vertical line and circle indicators (no packages)

- [x] Task 5: Create `RecipeVersionDiffScreen` (AC: #3, #4, #5)
  - [x] Create `app/lib/features/recipes/recipe_version_diff_screen.dart`
  - [x] StatefulWidget with `recipeId`, `versionId`, `versionNumber` constructor params
  - [x] Loads snapshot + current recipe in parallel via `Future.wait`
  - [x] Client-side diff: name, instructions, ingredients (by ingredient_id), steps (by step_number)
  - [x] Color coding: green=added, red=removed, amber=changed
  - [x] "Restore this version" stub button with SnackBar (wired in Story 4.3)
  - [x] Loading, error states

- [x] Task 6: Add routes to `app_router.dart` (AC: #1, #3)
  - [x] `/recipes/:id/versions` → `RecipeVersionHistoryScreen`
  - [x] `/recipes/:id/versions/:versionId` → `RecipeVersionDiffScreen`
  - [x] Both before `/recipes/:id` to avoid path conflicts
  - [x] Both screens imported

- [x] Task 7: Wire history navigation from recipe detail screen (AC: #2)
  - [x] Version badge taps call `context.push('/recipes/:id/versions', extra: {recipeName})`

- [x] Task 8: Add API tests for `GetRecipeVersion` (AC: #3)
  - [x] `test_get_recipe_version_success` — returns full snapshot
  - [x] `test_get_recipe_version_recipe_not_found` — 404 for unknown recipe
  - [x] `test_get_recipe_version_access_denied` — 403 for non-member
  - [x] `test_get_recipe_version_not_found` — 404 for unknown version

## Dev Notes

### Backend: `GetRecipeVersion` Endpoint

Follow exactly the same pattern as `GetRecipeVersions` (Story 4.1):

```python
# services/api/src/api/v1/recipe/get_recipe_version.py
class GetRecipeVersion(Endpoint):
    def execute(self, recipe_id: str, version_id: str):
        user: User = self.user
        recipe = self.database.find_by(Recipe, id=recipe_id)
        if not recipe: raise APIException(404, ...)
        membership = self.database.find_by(RecipeBookUser, user_id=user.id, recipe_book_id=recipe.recipe_book_id)
        if not membership: raise APIException(403, ...)
        version = self.database.find_by(RecipeVersion, id=version_id)
        if not version or str(version.recipe_id) != recipe_id:
            raise APIException(404, ...)
        return success(data=GetRecipeVersion.Response(
            id=str(version.id),
            version_number=version.version_number,
            snapshot=version.snapshot,
            changed_fields=version.changed_fields or [],
            created_at=version.created_at,
        ))

    class Response(BaseModel):
        id: str
        version_number: int
        snapshot: dict
        changed_fields: list[str] = []
        created_at: datetime
```

Router registration (add AFTER the existing `/recipes/{recipe_id}/versions` route):
```python
@router.get("/recipes/{recipe_id}/versions/{version_id}", ...)
async def get_recipe_version(...):
    return GetRecipeVersion(database=db, user=user).execute(recipe_id, version_id)
```

### Router: Route Ordering Matters

GoRouter in Flutter uses first-match routing. The routes must be in this order to avoid `/recipes/archived` and `/recipes/add/*` being shadowed by `/recipes/:id`:

The current router already has `/recipes/archived` and `/recipes/add/*` BEFORE `/recipes/:id`. The new `/recipes/:id/versions` and `/recipes/:id/versions/:versionId` routes must also come BEFORE `/recipes/:id` — or ideally use child routes. But since the current pattern registers them as top-level GoRoutes with `parentNavigatorKey: _rootNavigatorKey`, add them before the `/recipes/:id` route.

### Flutter: Diff Computation

Compute diffs client-side in `RecipeVersionDiffScreen._computeDiff()`. The snapshot from the API contains the **state before the edit** (i.e., the previous version's state). The current recipe data contains the **current state**.

```dart
// Ingredient diff
final snapshotIngredients = (snapshot['ingredients'] as List?) ?? [];
final currentIngredients = (currentRecipe['ingredients'] as List?) ?? [];
// Group by ingredient_id, compare quantity_display + unit_display
// Added = in current but not in snapshot
// Removed = in snapshot but not in current
// Changed = same ingredient_id but different quantity/unit
```

```dart
// Step diff
final snapshotSteps = (snapshot['steps'] as List?) ?? [];
final currentSteps = (currentRecipe['steps'] as List?) ?? [];
// Group by step_number, compare instruction text
// Added = step_number in current but not in snapshot
// Removed = step_number in snapshot but not in current
// Modified = same step_number but different instruction
```

Use simple green/red/amber color coding matching the existing Material 3 theme:
- Added: `colorScheme.primary` background (or `Colors.green.withValues(alpha: 0.15)`)
- Removed: `colorScheme.errorContainer` (or `Colors.red.withValues(alpha: 0.15)`)
- Changed: `Colors.amber.withValues(alpha: 0.15)`

### Flutter: Timeline Visual

Use a simple `IntrinsicHeight` + `Row` approach — a vertical line on the left, circle indicator at the version, content on the right. No external packages. Example structure:

```dart
Row(children: [
  Column(children: [
    Container(width: 2, height: 20, color: colorScheme.outlineVariant), // line above
    Container(width: 12, height: 12, decoration: BoxDecoration(shape: BoxShape.circle, color: colorScheme.primary)), // dot
    Expanded(child: Container(width: 2, color: colorScheme.outlineVariant)), // line below
  ]),
  const SizedBox(width: 12),
  Expanded(child: /* version card */),
])
```

### Flutter: `changed_fields` Label Mapping

Map internal field names to user-friendly labels:
```dart
const _fieldLabels = {
  'name': 'Name',
  'instructions': 'Instructions',
  'ingredients': 'Ingredients',
  'steps': 'Steps',
};
```

### Flutter: Route Extra Passing Pattern

When navigating to history screen from recipe detail:
```dart
context.push('/recipes/${widget.recipeId}/versions', extra: {'recipeName': _recipe!['name'] ?? ''});
```

In the router:
```dart
GoRoute(
  path: '/recipes/:id/versions',
  parentNavigatorKey: _rootNavigatorKey,
  builder: (context, state) {
    final id = state.pathParameters['id']!;
    final extra = state.extra as Map<String, dynamic>?;
    final recipeName = extra?['recipeName'] as String? ?? '';
    return RecipeVersionHistoryScreen(recipeId: id, recipeName: recipeName);
  },
),
GoRoute(
  path: '/recipes/:id/versions/:versionId',
  parentNavigatorKey: _rootNavigatorKey,
  builder: (context, state) {
    final id = state.pathParameters['id']!;
    final versionId = state.pathParameters['versionId']!;
    final extra = state.extra as Map<String, dynamic>?;
    final versionNumber = extra?['versionNumber'] as int? ?? 0;
    return RecipeVersionDiffScreen(recipeId: id, versionId: versionId, versionNumber: versionNumber);
  },
),
```

### Do Not:
- Implement "Restore this version" as more than a stub — that is Story 4.3
- Add any backend diff computation — diff is client-side
- Use any external diff/timeline packages — use plain Flutter widgets
- Modify the auto-save or version creation logic — that was Story 4.1
- Show the history badge if `version_count == null` — treat null as 0

### References

- [Source: services/api/src/api/v1/recipe/get_recipe_versions.py] — Pattern to follow for `GetRecipeVersion`
- [Source: services/api/src/routers/v1/recipe_router.py] — Route registration pattern
- [Source: app/lib/core/router/app_router.dart] — Route order and GoRoute registration patterns
- [Source: app/lib/features/recipes/recipe_detail_screen.dart] — Where to add version badge, `_InfoChip` pattern
- [Source: app/lib/core/services/api_client.dart] — API client pattern (`getRecipeVersions` for reference)
- [Source: app/lib/features/recipes/cook_mode/cook_mode_screen.dart] — StatefulWidget screen pattern
- [Source: _bmad-output/planning-artifacts/epics.md#Story-4.2] — Epic requirements
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md] — "Invisible versioning" UX principle, "zero git terminology"

### Project Structure Notes

New files:
- `services/api/src/api/v1/recipe/get_recipe_version.py`
- `app/lib/features/recipes/recipe_version_history_screen.dart`
- `app/lib/features/recipes/recipe_version_diff_screen.dart`

Modified files:
- `services/api/src/api/v1/recipe/__init__.py` — register `GetRecipeVersion`
- `services/api/src/routers/v1/recipe_router.py` — add route
- `app/lib/core/services/api_client.dart` — add `getRecipeVersion()`
- `app/lib/core/router/app_router.dart` — add two routes, import two screens
- `app/lib/features/recipes/recipe_detail_screen.dart` — add version badge and navigation

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

### Completion Notes List

- 209 API tests pass (4 new: test_get_recipe_version_success/recipe_not_found/access_denied/not_found)
- Flutter analyze clean — no errors introduced
- Diff is computed client-side by comparing snapshot (state before edit) to current recipe state
- `RecipeVersionDiffScreen` fetches both version snapshot and current recipe in parallel using `Future.wait`
- Route ordering: `/recipes/:id/versions` and `/recipes/:id/versions/:versionId` placed before `/recipes/:id` in app_router.dart
- `MockRecipeVersion` added to conftest.py for test reuse

### File List

**New files:**
- `services/api/src/api/v1/recipe/get_recipe_version.py` — GetRecipeVersion endpoint
- `app/lib/features/recipes/recipe_version_history_screen.dart` — version timeline UI
- `app/lib/features/recipes/recipe_version_diff_screen.dart` — diff viewer UI

**Modified files:**
- `services/api/src/api/v1/recipe/__init__.py` — registered GetRecipeVersion
- `services/api/src/routers/v1/recipe_router.py` — added GET /recipes/{id}/versions/{version_id} route
- `app/lib/core/services/api_client.dart` — added getRecipeVersion()
- `app/lib/core/router/app_router.dart` — added two new routes, imported new screens
- `app/lib/features/recipes/recipe_detail_screen.dart` — added version history badge
- `services/api/tests/test_recipe.py` — added TestGetRecipeVersion tests (4 tests)
- `services/api/tests/conftest.py` — added MockRecipeVersion

## Code Review Action Items

### Finding 1 — HIGH: `_buildIngredientsDiff` false positive on quantity comparison

**File:** `app/lib/features/recipes/recipe_version_diff_screen.dart` (line 232)

**Root cause:** `_create_version_snapshot` in `update_recipe.py` stored raw `str(ri.quantity_display)` (e.g., "0.5") while `get_recipe.py` returns `format_quantity(ri.quantity_display, ri.unit_display)` (e.g., "1/2" for fraction units). Direct string comparison produced false-positive diffs showing quantity as "changed" even when it was identical.

**Fix:** Changed `update_recipe.py` `_create_version_snapshot` to call `format_quantity(ri.quantity_display, ri.unit_display)` when building the snapshot, making the snapshot format consistent with the API response format. All 209 tests pass.

