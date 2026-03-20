# Story 10.1: Export Recipe Collection

Status: done

## Story

As a user,
I want to export my entire recipe collection as a JSON file,
so that I always own my data and can take it with me.

## Acceptance Criteria

1. **Export tile in Profile** — A tile "Export Collection" (under the existing "Recipes" section in `ProfileScreen`) tapping it triggers the export flow.
2. **Backend export endpoint** — `GET /v1/users/me/export` returns a JSON document containing all recipe books the user belongs to, with full recipe data: name, description, ingredients (with quantities/units), steps, tags, notes, version history, and book assignments.
3. **File sharing via OS share sheet** — On success, the app encodes the JSON and invokes `SharePlus.instance.share(ShareParams(files: [XFile.fromData(...)]))` so the user can save to Files, AirDrop, email, etc.
4. **Export includes ALL data** — Nothing omitted or altered: `name`, `description`, `instructions`, `servings`, `prep_time`, `cook_time`, `image_url`, `source_url`, `tags`, `ingredients` (with `canonical_name`, `quantity_display`, `unit_display`), `steps`, `notes`, `versions`, `forked_from_*` lineage fields, `recipe_book_id`, and `created_at`/`updated_at` timestamps.
5. **Data sovereignty guarantee** — No authentication failure, rate-limit, or permission check can block the export for a logged-in user. The endpoint only exports books/recipes the user is an actual member of.
6. **Loading and error state** — While the export runs, the tile shows a loading indicator (or is disabled). On API error, a snackbar shows "Export failed — please try again".
7. **Backend tests** — `test_export_recipes.py` covers: success returns all user's books/recipes, empty collection returns empty data, response structure matches schema.

## Tasks / Subtasks

- [x] Task 1: Backend — `ExportRecipes` endpoint (AC: 2, 4, 5)
  - [x] Create `services/api/src/api/v1/user/export_recipes.py` with `ExportRecipes(Endpoint)` class
  - [x] Query all `RecipeBookUser` rows for `user_id == user.id` (non-archived books) to get accessible books
  - [x] For each book, load recipes with eager-joined `ingredients`, `steps`, `notes`, `versions`
  - [x] Return structured JSON: `{exported_at, recipe_count, book_count, books: [{id, name, role, recipes: [{...full recipe...}]}]}`
  - [x] Register in `services/api/src/api/v1/user/__init__.py`
  - [x] Add route in `services/api/src/routers/v1/user_router.py`: `GET /v1/users/me/export`

- [x] Task 2: Backend tests (AC: 7)
  - [x] Create `services/api/tests/test_export_recipes.py`
  - [x] Test: success — returns correct book_count, recipe_count, book/recipe structure
  - [x] Test: empty collection — returns `book_count=0, recipe_count=0, books=[]`
  - [x] Test: unauthenticated — 401 (handled by framework, no extra test needed)

- [x] Task 3: Flutter — `exportRecipes()` in `ApiClient` (AC: 3)
  - [x] In `app/lib/core/services/api_client.dart`, add after existing user methods:
    ```dart
    Future<Response> exportRecipes() {
      return _dio.get('/v1/users/me/export');
    }
    ```

- [x] Task 4: Flutter — export tile and logic in `ProfileScreen` (AC: 1, 3, 6)
  - [x] In `app/lib/features/profile/profile_screen.dart`:
    - Add `bool _isExporting = false;` state field
    - Add `_exportCollection()` method (see Dev Notes for full implementation)
    - In the Recipes section (after "Archived Recipes" tile), add the Export tile using `_buildProfileTile`
  - [x] Use `Icons.download_outlined` icon
  - [x] Tile shows loading indicator when `_isExporting == true` (pass `_isExporting ? null : _exportCollection` to `onTap`)

- [x] Task 5: Flutter widget tests (AC: 1, 6)
  - [x] Create `app/test/features/profile/export_collection_test.dart`
  - [x] Test: "Export Collection" tile is visible in the Recipes section
  - [x] Test: tapping tile calls `exportRecipes()` on the API client
  - [x] Test: error shows "Export failed — please try again" snackbar

## Dev Notes

### Backend: `ExportRecipes` Endpoint

**File:** `services/api/src/api/v1/user/export_recipes.py`

```python
"""Export all user recipe data as JSON."""

from datetime import UTC, datetime

from pydantic import BaseModel
from utils.api.endpoint import Endpoint, success
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.recipe import Recipe
from utils.models.recipe_ingredient import RecipeIngredient
from utils.models.recipe_note import RecipeNote
from utils.models.recipe_step import RecipeStep
from utils.models.recipe_version import RecipeVersion
from utils.models.user import User


class ExportRecipes(Endpoint):
    """Export user's entire recipe collection as JSON."""

    def execute(self):
        user: User = self.user

        # Find all book memberships for this user
        memberships = (
            self.db.query(RecipeBookUser)
            .filter(RecipeBookUser.user_id == user.id)
            .all()
        )

        books_data = []
        total_recipe_count = 0

        for membership in memberships:
            book = self.database.find_by(RecipeBook, id=membership.recipe_book_id)
            if not book or book.archived_at:
                continue

            # Get all non-archived recipes in this book
            recipes = (
                self.db.query(Recipe)
                .filter(Recipe.recipe_book_id == book.id)
                .filter(Recipe.archived_at.is_(None))
                .all()
            )

            recipes_data = []
            for recipe in recipes:
                steps = (
                    self.db.query(RecipeStep)
                    .filter(RecipeStep.recipe_id == recipe.id)
                    .order_by(RecipeStep.step_number)
                    .all()
                )
                ingredients = (
                    self.db.query(RecipeIngredient)
                    .filter(RecipeIngredient.recipe_id == recipe.id)
                    .filter(RecipeIngredient.archived_at.is_(None))
                    .all()
                )
                notes = (
                    self.db.query(RecipeNote)
                    .filter(RecipeNote.recipe_id == recipe.id)
                    .filter(RecipeNote.archived_at.is_(None))
                    .all()
                )
                versions = (
                    self.db.query(RecipeVersion)
                    .filter(RecipeVersion.recipe_id == recipe.id)
                    .order_by(RecipeVersion.version_number)
                    .all()
                )

                recipes_data.append({
                    "id": str(recipe.id),
                    "name": recipe.name,
                    "description": recipe.description,
                    "instructions": recipe.instructions,
                    "servings": recipe.servings,
                    "prep_time": recipe.prep_time,
                    "cook_time": recipe.cook_time,
                    "image_url": recipe.image_url,
                    "source_url": recipe.source_url,
                    "tags": recipe.tags or [],
                    "forked_from_recipe_id": str(recipe.forked_from_recipe_id) if recipe.forked_from_recipe_id else None,
                    "forked_from_book_id": str(recipe.forked_from_book_id) if recipe.forked_from_book_id else None,
                    "forked_from_recipe_name": recipe.forked_from_recipe_name,
                    "forked_from_book_name": recipe.forked_from_book_name,
                    "created_at": recipe.created_at.isoformat(),
                    "updated_at": recipe.updated_at.isoformat(),
                    "ingredients": [
                        {
                            "canonical_name": ri.ingredient.canonical_name if ri.ingredient else None,
                            "quantity_display": float(ri.quantity_display) if ri.quantity_display else None,
                            "unit_display": ri.unit_display,
                            "notes": ri.notes,
                        }
                        for ri in ingredients
                    ],
                    "steps": [
                        {
                            "step_number": s.step_number,
                            "instruction": s.instruction,
                            "duration_minutes": s.duration_minutes,
                        }
                        for s in steps
                    ],
                    "notes": [
                        {
                            "content": n.content,
                            "created_at": n.created_at.isoformat(),
                        }
                        for n in notes
                    ],
                    "versions": [
                        {
                            "version_number": v.version_number,
                            "snapshot": v.snapshot,
                            "created_at": v.created_at.isoformat(),
                        }
                        for v in versions
                    ],
                })

            total_recipe_count += len(recipes_data)
            books_data.append({
                "id": str(book.id),
                "name": book.name,
                "description": book.description,
                "role": membership.role,
                "recipes": recipes_data,
            })

        return success(
            data=ExportRecipes.Response(
                exported_at=datetime.now(UTC).isoformat(),
                recipe_count=total_recipe_count,
                book_count=len(books_data),
                books=books_data,
            )
        )

    class Response(BaseModel):
        exported_at: str
        recipe_count: int
        book_count: int
        books: list[dict]
```

**Router Registration** (`services/api/src/routers/v1/user_router.py`):
```python
from api.v1.user.export_recipes import ExportRecipes

@user_router.get("/me/export")
async def export_recipes(
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Export the user's entire recipe collection as JSON."""
    return ExportRecipes.call(user=user, database=database)
```

**Important:** Check if `api/v1/user/` directory exists. Looking at the existing structure, user endpoints may be inline in the router rather than in a separate `api/v1/user/` module. Check `services/api/src/api/v1/` directory and follow the pattern used by existing user-related endpoints.

### Backend: `RecipeIngredient` model field notes

- `ri.ingredient` may need a joined query or the ingredient may not be eager-loaded. Safe pattern: filter out `ri.ingredient is None`.
- `RecipeIngredient` has: `quantity_display` (Decimal), `unit_display` (str), `notes` (str|None)
- `RecipeIngredient` also has: `ingredient_id` FK → `Ingredient.canonical_name`

Check `services/api/src/api/v1/recipe/get_recipe.py` for the established pattern of loading recipe ingredients with their linked `Ingredient`.

### Backend: Check `RecipeNote` fields

Verify field names from `libraries/utils/utils/models/recipe_note.py`:
- Likely: `content`, `recipe_id`, `created_at`

### Backend: Check `RecipeVersion` fields

Verify from `libraries/utils/utils/models/recipe_version.py`:
- Likely: `version_number`, `snapshot` (JSON/dict), `recipe_id`, `created_at`

### Backend: Check `RecipeStep` fields

From the model:
- `step_number` (int), `instruction` (str), `duration_minutes` (int|None)

### Flutter: `_exportCollection()` Method

Add to `_ProfileScreenState` in `profile_screen.dart`:

```dart
Future<void> _exportCollection() async {
  setState(() => _isExporting = true);
  try {
    final response = await getIt<ApiClient>().exportRecipes();
    final jsonString = jsonEncode(response.data);
    final bytes = Uint8List.fromList(utf8.encode(jsonString));
    final timestamp = DateTime.now().toIso8601String().replaceAll(':', '-').substring(0, 19);
    await SharePlus.instance.share(ShareParams(
      files: [
        XFile.fromData(
          bytes,
          name: 'palateful_recipes_$timestamp.json',
          mimeType: 'application/json',
        )
      ],
      subject: 'My Palateful Recipe Collection',
    ));
  } catch (_) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Export failed — please try again')),
      );
    }
  } finally {
    if (mounted) setState(() => _isExporting = false);
  }
}
```

**Required imports for profile_screen.dart:**
```dart
import 'dart:convert';
import 'dart:typed_data';
import 'package:share_plus/share_plus.dart';
```

`share_plus` is already in `pubspec.yaml` (`^10.1.4`). `SharePlus` and `ShareParams` are available in share_plus v10+.

**Export tile in Recipes section** (after Archived Recipes tile):
```dart
const SizedBox(height: 8),
_buildProfileTile(
  icon: Icons.download_outlined,
  label: 'Export Collection',
  value: _isExporting ? 'Exporting...' : 'Download all your recipes as JSON',
  onTap: _isExporting ? () {} : _exportCollection,
  colorScheme: colorScheme,
  textTheme: textTheme,
),
```

### Flutter: Test Pattern

Follow `notification_preferences_screen.dart` style for profile tests. The profile screen uses `getIt<ApiClient>()` directly in the export method, so the test must register a fake `ApiClient` in GetIt before pumping the widget.

**`app/test/features/profile/export_collection_test.dart`:**

```dart
import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/profile/profile_screen.dart';

Response<dynamic> _fakeResponse(dynamic data) => Response(
  data: data, requestOptions: RequestOptions(path: ''), statusCode: 200,
);

class _FakeApiClient extends ApiClient {
  bool exportCalled = false;
  bool shouldThrow = false;

  @override
  Future<Response> exportRecipes() async {
    exportCalled = true;
    if (shouldThrow) throw Exception('network error');
    return _fakeResponse({
      'exported_at': '2026-03-19T12:00:00Z',
      'recipe_count': 3,
      'book_count': 1,
      'books': [],
    });
  }
}
```

Note: `SharePlus.instance.share(...)` cannot be fully tested in widget tests (it invokes platform channels). Mock or skip the share call assertion — focus on API call and snackbar.

### Backend Test Pattern (`test_export_recipes.py`)

Follow `test_populate_from_recipe.py` pattern. Key mocks:
- `MockRecipeBookUser` from `conftest.py` (has `user_id`, `recipe_book_id`, `role`)
- `MockRecipeBook` from `conftest.py`
- `MockRecipe`, `MockRecipeIngredient`, `MockRecipeStep` from `conftest.py`

The endpoint calls `self.db.query()` multiple times (for RecipeBookUser, Recipe, RecipeStep, etc.). Use `mock_db.db.query.side_effect = [MockQuery([membership]), MockQuery([book]), MockQuery([recipe]), ...]` pattern (see `test_recipe_book.py:96`).

Backend endpoint URL: `GET /v1/users/me/export`

### Check: Does `api/v1/user/` directory exist?

Inspect `services/api/src/api/v1/` directory at implementation time. If no `user/` subdirectory exists, you have two options:
1. Create `api/v1/user/` subdirectory + `__init__.py` (preferred for consistency)
2. Inline the logic in `user_router.py` directly (simpler if only one user-specific endpoint)

Look at how neighboring routers like `user_router.py` import their handler classes for the established pattern.

### Project Structure Notes

**New files:**
- `services/api/src/api/v1/user/export_recipes.py`
- `services/api/src/api/v1/user/__init__.py` (if directory is new)
- `services/api/tests/test_export_recipes.py`
- `app/test/features/profile/export_collection_test.dart`

**Modified files:**
- `services/api/src/routers/v1/user_router.py` — add `GET /v1/users/me/export` route
- `app/lib/core/services/api_client.dart` — add `exportRecipes()` method
- `app/lib/features/profile/profile_screen.dart` — add tile + `_exportCollection()` method

### References

- Epic 10 story: `_bmad-output/planning-artifacts/epics.md` (line 1068)
- Existing user router: `services/api/src/routers/v1/user_router.py`
- Recipe model: `libraries/utils/utils/models/recipe.py`
- RecipeBookUser model: `libraries/utils/utils/models/recipe_book_user.py`
- RecipeIngredient model: `libraries/utils/utils/models/recipe_ingredient.py`
- RecipeStep model: `libraries/utils/utils/models/recipe_step.py`
- RecipeNote model: `libraries/utils/utils/models/recipe_note.py`
- RecipeVersion model: `libraries/utils/utils/models/recipe_version.py`
- Endpoint class pattern: `services/api/src/api/v1/recipe/get_recipe.py`
- Backend test pattern: `services/api/tests/test_populate_from_recipe.py`
- MockQuery pattern: `services/api/tests/test_recipe_book.py:96`
- share_plus usage: `app/lib/features/recipe_books/recipe_book_members_screen.dart`
- Profile screen: `app/lib/features/profile/profile_screen.dart`
- ApiClient: `app/lib/core/services/api_client.dart`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- `share_plus` v10.x uses `Share.shareXFiles([XFile.fromData(...)])` not `SharePlus.instance.share(ShareParams(...))` as the dev notes suggested
- `RecipeNote` has `body` field (not `content` as in dev notes)
- `RecipeStep` has `active_time_minutes` (not `duration_minutes`); exported as `duration_minutes` key
- `database.where()` automatically excludes archived records — no need for explicit `archived_at.is_(None)` filters in most calls
- Backend test response structure: `response.json()` is the data directly (not `response.json()["data"]`), because `Endpoint.handle_result()` uses `content=jsonable_encoder(result['data'])`
- Flutter tests require both `ApiClient` and `AuthService` registered in GetIt; `ProfileScreen` uses both
- Export tile is off-screen in tests — use `tester.ensureVisible()` before `tester.tap()`

### File List

- `services/api/src/api/v1/user/export_recipes.py` — new: `ExportRecipes` endpoint
- `services/api/src/api/v1/user/__init__.py` — added `ExportRecipes` export
- `services/api/src/routers/v1/user_router.py` — added `GET /me/export` route
- `services/api/tests/test_export_recipes.py` — new: 6 backend tests
- `app/lib/core/services/api_client.dart` — added `exportRecipes()` method
- `app/lib/features/profile/profile_screen.dart` — added `_isExporting`, `_exportCollection()`, export tile
- `app/test/features/profile/export_collection_test.dart` — new: 3 Flutter widget tests
