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
      'ingredients': [],
      'steps': [],
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
  bool shareRecipeCalled = false;
  bool revokeRecipeShareCalled = false;
  bool shouldThrowShare = false;

  @override
  Future<Response> getRecipe(String recipeId) async =>
      _fakeResponse(_fakeRecipeData(recipeId: recipeId));

  @override
  Future<Response> shareRecipe(String recipeId) async {
    shareRecipeCalled = true;
    if (shouldThrowShare) throw Exception('network error');
    return _fakeResponse({
      'token': 'tok12345678901234',
      'deep_link': 'palateful://recipe-public/tok12345678901234',
    });
  }

  @override
  Future<Response> revokeRecipeShare(String recipeId) async {
    revokeRecipeShareCalled = true;
    return _fakeResponse({'success': true});
  }
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

  group('Share Link via popup menu', () {
    testWidgets('tapping "Share Link" calls shareRecipe() on the API client',
        (tester) async {
      final fakeClient =
          GetIt.instance<ApiClient>() as _FakeApiClient;

      await tester.pumpWidget(const MaterialApp(
        home: RecipeDetailScreen(recipeId: 'recipe-1'),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Open popup menu
      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();

      // Tap "Share Link"
      await tester.tap(find.text('Share Link'));
      await tester.pumpAndSettle();

      expect(fakeClient.shareRecipeCalled, isTrue);
    });

    testWidgets('bottom sheet appears with the deep link after sharing',
        (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: RecipeDetailScreen(recipeId: 'recipe-1'),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Share Link'));
      await tester.pumpAndSettle();

      expect(find.text('Public Link'), findsOneWidget);
      expect(
        find.text('palateful://recipe-public/tok12345678901234'),
        findsOneWidget,
      );
    });

    testWidgets('tapping "Copy Link" shows "Copied!" snackbar',
        (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: RecipeDetailScreen(recipeId: 'recipe-1'),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Share Link'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Copy Link'));
      await tester.pumpAndSettle();

      expect(find.text('Copied!'), findsOneWidget);
    });

    testWidgets('tapping "Revoke" calls revokeRecipeShare()',
        (tester) async {
      final fakeClient =
          GetIt.instance<ApiClient>() as _FakeApiClient;

      await tester.pumpWidget(const MaterialApp(
        home: RecipeDetailScreen(recipeId: 'recipe-1'),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Share Link'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Revoke'));
      await tester.pumpAndSettle();

      expect(fakeClient.revokeRecipeShareCalled, isTrue);
    });

    testWidgets('error shows "Failed to generate share link" snackbar',
        (tester) async {
      final fakeClient =
          GetIt.instance<ApiClient>() as _FakeApiClient;
      fakeClient.shouldThrowShare = true;

      await tester.pumpWidget(const MaterialApp(
        home: RecipeDetailScreen(recipeId: 'recipe-1'),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Share Link'));
      await tester.pumpAndSettle();

      expect(
        find.text('Failed to generate share link'),
        findsOneWidget,
      );
    });
  });
}
