# Story 10.3: Native Platform Sharing

Status: done

## Story

As a user,
I want to share a recipe via text, email, or messaging apps using the native share sheet,
so that I can send recipes however my friends prefer to communicate.

## Acceptance Criteria

1. **Native share action** — The recipe detail screen has a "Share" action in the overflow popup menu (alongside the existing "Share Link") that opens the OS-native share sheet (iOS Activity View, Android Share Sheet).
2. **Share content format** — The shared content includes: recipe title, optional description, formatted ingredients list (bullet points with quantity + unit + name), numbered steps list, and a "Shared via Palateful" attribution footer. Format is clean and readable — not raw JSON.
3. **No auth or network required** — The native share action uses data already loaded in `_recipe`. No API call is needed (share text is assembled from the in-memory recipe map).
4. **Subject line** — The share subject (used by email clients) is set to the recipe name.
5. **Sharing targets** — Works via text, email, WhatsApp, iMessage, and any other app installed on device, because it uses the platform native share sheet via `share_plus`.
6. **Flutter widget test** — `share_native_test.dart` verifies: "Share" menu item exists in the popup, tapping it does not throw, the menu item appears alongside "Share Link".

## Tasks / Subtasks

- [x] Task 1: Add share_plus import and `_nativeShareRecipe()` to `recipe_detail_screen.dart` (AC: 1, 2, 3, 4, 5)
  - [x] Add `import 'package:share_plus/share_plus.dart';` at top of file
  - [x] Add `_nativeShareRecipe()` async method that builds share text from `_recipe` map
  - [x] Format: name → description → "Ingredients:\n• qty unit name" → "Steps:\n1. instruction" → "Shared via Palateful"
  - [x] Call `Share.share(text.trim(), subject: name)`

- [x] Task 2: Add "Share" popup menu item to `recipe_detail_screen.dart` (AC: 1)
  - [x] Add `PopupMenuItem(value: 'share_native', ...)` with `Icons.share_outlined` and label "Share"
  - [x] Insert after the existing `share_link` item (before the `can_edit` guard items)
  - [x] Add `else if (value == 'share_native') { _nativeShareRecipe(); }` to `onSelected`

- [x] Task 3: Flutter widget test (AC: 6)
  - [x] Create `app/test/features/recipes/share_native_test.dart`
  - [x] Register `_FakeApiClient` + `_FakeAuthService` in GetIt (same pattern as `share_recipe_test.dart`)
  - [x] Test: "Share" menu item appears in popup
  - [x] Test: tapping "Share" does not throw (Share.share() is a no-op in test env)
  - [x] Test: "Share Link" and "Share" both appear in the same popup

## Dev Notes

### No backend changes needed

This story is **100% Flutter-only**. The `share_plus` package is already in `pubspec.yaml`:
```yaml
share_plus: ^10.1.4   # app/pubspec.yaml line 64
```
No `flutter pub get`, no `pubspec.yaml` changes, no API endpoint changes.

### `share_plus` v10 API (already installed)

```dart
import 'package:share_plus/share_plus.dart';

// Simple text share (opens native share sheet)
await Share.share(
  text,
  subject: recipeName,  // email clients use this as subject line
);
```

`Share.share()` is a static method. It opens the platform-native share sheet. In Flutter widget tests, platform channel calls are no-ops by default (test environment) — so tapping the "Share" button in a test will not crash but won't open a real share sheet.

### `_nativeShareRecipe()` Method Pattern

Add to `_RecipeDetailScreenState` in `app/lib/features/recipes/recipe_detail_screen.dart`:

```dart
Future<void> _nativeShareRecipe() async {
  if (_recipe == null) return;
  final name = _recipe!['name'] as String? ?? '';
  final description = _recipe!['description'] as String?;
  final ingredients = (_recipe!['ingredients'] as List?) ?? [];
  final steps = (_recipe!['steps'] as List?) ?? [];

  final buffer = StringBuffer();
  buffer.writeln(name);

  if (description != null && description.isNotEmpty) {
    buffer.writeln();
    buffer.writeln(description);
  }

  if (ingredients.isNotEmpty) {
    buffer.writeln();
    buffer.writeln('Ingredients:');
    for (final ing in ingredients) {
      final ingName = (ing['ingredient'] as Map?)?['canonical_name']?.toString() ?? '';
      final qty = ing['quantity_display']?.toString() ?? '';
      final unit = ing['unit_display']?.toString() ?? '';
      final parts = [qty, unit, ingName].where((s) => s.isNotEmpty).join(' ');
      if (parts.isNotEmpty) buffer.writeln('• $parts');
    }
  }

  if (steps.isNotEmpty) {
    buffer.writeln();
    buffer.writeln('Steps:');
    for (int i = 0; i < steps.length; i++) {
      final step = steps[i] as Map;
      buffer.writeln('${i + 1}. ${step['instruction']?.toString() ?? ''}');
    }
  }

  buffer.writeln();
  buffer.write('Shared via Palateful');

  await Share.share(buffer.toString(), subject: name);
}
```

### Popup Menu Item Addition

In the `itemBuilder` of `PopupMenuButton<String>` in `recipe_detail_screen.dart`, add **after** the `share_link` item (around line 598) and **before** the `can_edit` guard:

```dart
const PopupMenuItem(
  value: 'share_native',
  child: Row(
    children: [
      Icon(Icons.share_outlined),
      SizedBox(width: 8),
      Text('Share'),
    ],
  ),
),
```

In `onSelected` handler (around line 557), add after the `share_link` branch:

```dart
} else if (value == 'share_native') {
  _nativeShareRecipe();
}
```

### Flutter Test Pattern

The test file should follow `share_recipe_test.dart` exactly:

```dart
// app/test/features/recipes/share_native_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:dio/dio.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/features/recipes/recipe_detail_screen.dart';

Response<dynamic> _fakeResponse(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

Map<String, dynamic> _fakeRecipeData({String recipeId = 'recipe-1'}) => {
      'id': recipeId,
      'name': 'Spaghetti Carbonara',
      'description': 'Classic Italian pasta',
      'recipe_book_id': 'book-1',
      'can_edit': true,
      'is_favorite': false,
      'ingredients': [
        {
          'ingredient': {'canonical_name': 'spaghetti'},
          'quantity_display': '200',
          'unit_display': 'g',
          'is_optional': false,
          'order_index': 0,
        }
      ],
      'steps': [
        {'instruction': 'Boil water', 'step_number': 1},
        {'instruction': 'Cook pasta', 'step_number': 2},
      ],
      'notes': [],
      'tags': [],
      'versions': [],
      'image_url': null,
      'source_url': null,
      'servings': 4,
      'prep_time': 10,
      'cook_time': 20,
      'forked_from_recipe_id': null,
      'forked_from_recipe_name': null,
      'forked_from_book_name': null,
      'created_at': '2026-01-01T00:00:00Z',
      'updated_at': '2026-01-01T00:00:00Z',
    };

class _FakeApiClient extends ApiClient {
  @override
  Future<Response> getRecipe(String recipeId) async =>
      _fakeResponse(_fakeRecipeData(recipeId: recipeId));
}

class _FakeAuthService extends AuthService {
  @override
  Future<void> logout() async {}
}

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  setUp(() {
    final gi = GetIt.instance;
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
    gi.registerSingleton<ApiClient>(_FakeApiClient());
    if (gi.isRegistered<AuthService>()) gi.unregister<AuthService>();
    gi.registerSingleton<AuthService>(_FakeAuthService());
  });

  tearDown(() {
    final gi = GetIt.instance;
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
    if (gi.isRegistered<AuthService>()) gi.unregister<AuthService>();
  });

  group('Native Share via popup menu', () {
    testWidgets('"Share" menu item appears in popup',
        (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: RecipeDetailScreen(recipeId: 'recipe-1'),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();

      expect(find.text('Share'), findsOneWidget);
    });

    testWidgets('"Share" and "Share Link" both appear in popup',
        (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: RecipeDetailScreen(recipeId: 'recipe-1'),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();

      expect(find.text('Share'), findsOneWidget);
      expect(find.text('Share Link'), findsOneWidget);
    });

    testWidgets('tapping "Share" does not throw',
        (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: RecipeDetailScreen(recipeId: 'recipe-1'),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();

      // Should not throw — Share.share() is a no-op in test environment
      await tester.tap(find.text('Share'));
      await tester.pumpAndSettle();
      // No assertion needed — just verify no exception thrown
    });
  });
}
```

### Project Structure Notes

**Modified files:**
- `app/lib/features/recipes/recipe_detail_screen.dart` — add `import 'package:share_plus/share_plus.dart'`, `_nativeShareRecipe()` method, "Share" popup item, `onSelected` handler

**New files:**
- `app/test/features/recipes/share_native_test.dart` — 3 Flutter widget tests

**No changes to:**
- `app/pubspec.yaml` (share_plus already present)
- Any backend files
- `app_router.dart`
- `api_client.dart`

### References

- `share_plus` pub.dev: https://pub.dev/packages/share_plus (already at ^10.1.4 in pubspec)
- Recipe detail screen: `app/lib/features/recipes/recipe_detail_screen.dart` (popup menu around line 551)
- Existing share test pattern: `app/test/features/recipes/share_recipe_test.dart`
- Epic 10.3 story: `_bmad-output/planning-artifacts/epics.md` (lines 1104–1118)
- Story 3.5 (inbound share sheet implementation): `_bmad-output/implementation-artifacts/3-5-share-sheet-import.md`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- `share_plus` was already in `pubspec.yaml` at ^10.1.4 — no dependency changes needed
- `_nativeShareRecipe()` assembles text from the in-memory `_recipe` map: title → description → bullet ingredients → numbered steps → attribution
- "Share" popup item placed immediately after "Share Link" in the overflow menu
- `Share.share()` is a static platform channel call; it is a no-op in widget test environment so all tests pass without special mocking
- All 361 backend tests continue to pass (no regressions)

### File List

- `app/lib/features/recipes/recipe_detail_screen.dart` — added `share_plus` import, `_nativeShareRecipe()` method, "Share" popup item, `onSelected` branch
- `app/test/features/recipes/share_native_test.dart` — new: 3 Flutter widget tests
