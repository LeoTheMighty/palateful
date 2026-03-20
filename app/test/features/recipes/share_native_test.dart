import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/features/recipes/recipe_detail_screen.dart';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

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
    testWidgets('"Share" menu item appears in popup', (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: RecipeDetailScreen(recipeId: 'recipe-1'),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();

      expect(find.text('Share'), findsOneWidget);
    });

    testWidgets('"Share" and "Share Link" both appear in popup', (tester) async {
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

    testWidgets('tapping "Share" does not throw', (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: RecipeDetailScreen(recipeId: 'recipe-1'),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();

      // Share.share() is a no-op in test environment — should not throw
      await tester.tap(find.text('Share'));
      await tester.pumpAndSettle();
    });
  });
}
