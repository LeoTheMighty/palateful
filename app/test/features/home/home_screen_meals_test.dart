// md-4: Home grid + favorites carousel render Meals alongside recipes.
//
// Load-bearing invariant: a zero-Meal fixture must render bit-identical
// to pre-epic (no MealTile in tree, no empty section).

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/core/services/shared_state_service.dart';
import 'package:palateful/features/home/home_screen.dart';
import 'package:palateful/features/meals/widgets/meal_tile.dart';
import 'package:palateful/features/home/widgets/recipe_card.dart';
import 'package:palateful/features/recipes/add_recipe/batch_parser_service.dart';
import 'package:palateful/features/recipe_books/services/recipe_book_service.dart';

Response<dynamic> _fakeResponse(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

/// A fake API client that returns deterministic mixed recipe + meal
/// payloads. Each test supplies its own `recipes` + `meals` lists; the
/// fake wires them into `getRecipeBooks` (as one book with `recipes`)
/// and `listMeals(scope:'home')`.
class _FakeApiClient extends ApiClient {
  final List<Map<String, dynamic>> recipes;
  final List<Map<String, dynamic>> meals;
  final List<Map<String, dynamic>> favoritedMeals;

  _FakeApiClient({
    this.recipes = const [],
    this.meals = const [],
    this.favoritedMeals = const [],
  });

  @override
  Future<Response> getRecipeBooks({int limit = 20, int offset = 0}) async =>
      _fakeResponse({
        'items': [
          {'id': 'book-1', 'name': 'Dinners'}
        ]
      });

  @override
  Future<Response> getRecipeBook(String id) async => _fakeResponse({
        'id': id,
        'name': 'Dinners',
        'recipes': recipes,
      });

  @override
  Future<Response> getFavorites() async => _fakeResponse({
        'items': <Map<String, dynamic>>[],
        'total': 0,
        'favorited_meals': favoritedMeals,
      });

  @override
  Future<Response> listMeals({
    int? limit,
    int offset = 0,
    bool includeArchived = false,
    bool? archived,
    String? scope,
    String? q,
  }) async =>
      _fakeResponse({'items': meals, 'total': meals.length});

  @override
  Future<Response> getMealEventsForToday() async =>
      _fakeResponse({'items': <Map<String, dynamic>>[], 'total': 0});

  @override
  Future<Response> getRecentlyCookedRecipes({int limit = 5}) async =>
      _fakeResponse({'items': <Map<String, dynamic>>[], 'total': 0});
}

void _registerFakes(_FakeApiClient client) {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  gi.registerSingleton<ApiClient>(client);
  if (gi.isRegistered<BatchParserService>()) gi.unregister<BatchParserService>();
  gi.registerLazySingleton<BatchParserService>(() => BatchParserService());
  if (gi.isRegistered<RecipeBookService>()) {
    gi.unregister<RecipeBookService>();
  }
  gi.registerLazySingleton<RecipeBookService>(() => RecipeBookService(client));
  if (gi.isRegistered<AuthService>()) gi.unregister<AuthService>();
  gi.registerSingleton<AuthService>(AuthService());
  if (gi.isRegistered<SharedStateService>()) {
    gi.unregister<SharedStateService>();
  }
  gi.registerSingleton<SharedStateService>(SharedStateService());
}

void _unregister() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  if (gi.isRegistered<BatchParserService>()) {
    gi.unregister<BatchParserService>();
  }
  if (gi.isRegistered<AuthService>()) gi.unregister<AuthService>();
  if (gi.isRegistered<SharedStateService>()) {
    gi.unregister<SharedStateService>();
  }
}

Map<String, dynamic> _recipe({
  required String id,
  required String name,
  String updatedAt = '2026-04-01T00:00:00Z',
}) =>
    {
      'id': id,
      'name': name,
      'recipe_book_id': 'book-1',
      'recipe_book_name': 'Dinners',
      'updated_at': updatedAt,
      'created_at': updatedAt,
      'tags': <String>[],
    };

Map<String, dynamic> _mealSummary({
  required String id,
  required String name,
  String updatedAt = '2026-04-18T00:00:00Z',
  int componentCount = 2,
  List<String>? images,
}) =>
    {
      'id': id,
      'name': name,
      'recipe_book_id': 'book-1',
      'component_count': componentCount,
      'component_image_urls': images ?? <String>[],
      'updated_at': updatedAt,
      'archived_at': null,
    };

Future<void> _pumpHome(WidgetTester tester) async {
  tester.view.physicalSize = const Size(1080, 2400);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(() {
    tester.view.resetPhysicalSize();
    tester.view.resetDevicePixelRatio();
  });
  await tester.pumpWidget(const ProviderScope(
    child: MaterialApp(home: HomeScreen()),
  ));
  // Let in-flight async work settle. pumpAndSettle drains every future +
  // animation frame; the trailing 300ms pump covers the 250ms debounce
  // on SharedStateService.syncRecipeBooks so the test doesn't leak a
  // pending timer into the next run.
  await tester.pumpAndSettle();
  await tester.pump(const Duration(milliseconds: 300));
}

void main() {
  setUpAll(() async {
  });

  tearDown(_unregister);

  group('HomeScreen — md-4 Meals in grid', () {
    testWidgets('zero-Meal fixture renders no MealTile (zero-regression)',
        (tester) async {
      _registerFakes(_FakeApiClient(
        recipes: [
          _recipe(id: 'r1', name: 'Pasta'),
          _recipe(id: 'r2', name: 'Salad'),
        ],
      ));
      await _pumpHome(tester);
      expect(find.byType(MealTile), findsNothing);
      expect(find.byType(RecipeCard), findsWidgets);
    });

    testWidgets('mixed fixture renders both tile types', (tester) async {
      _registerFakes(_FakeApiClient(
        recipes: [_recipe(id: 'r1', name: 'Pasta')],
        meals: [_mealSummary(id: 'm1', name: 'Kale Salad Meal')],
      ));
      await _pumpHome(tester);

      expect(find.byType(RecipeCard), findsOneWidget);
      expect(find.byType(MealTile), findsOneWidget);
    });

    testWidgets('meals-only fixture renders only MealTiles', (tester) async {
      _registerFakes(_FakeApiClient(
        meals: [
          _mealSummary(id: 'm1', name: 'Kale Salad Meal'),
          _mealSummary(id: 'm2', name: 'Breakfast Spread'),
        ],
      ));
      await _pumpHome(tester);

      expect(find.byType(RecipeCard), findsNothing);
      expect(find.byType(MealTile), findsNWidgets(2));
    });

    testWidgets('merged list is sorted by updated_at DESC', (tester) async {
      _registerFakes(_FakeApiClient(
        recipes: [
          _recipe(
            id: 'r-older',
            name: 'Older Recipe',
            updatedAt: '2026-01-01T00:00:00Z',
          ),
        ],
        meals: [
          _mealSummary(
            id: 'm-newest',
            name: 'Newest Meal',
            updatedAt: '2026-05-01T00:00:00Z',
          ),
        ],
      ));
      await _pumpHome(tester);

      // Meal (newer) should render at grid slot 0; recipe (older) at
      // slot 1. In a 2-column grid that means meal at the left column,
      // recipe at the right — same y, smaller x.
      final mealFinder = find.byType(MealTile);
      final recipeFinder = find.byType(RecipeCard);
      expect(mealFinder, findsOneWidget);
      expect(recipeFinder, findsOneWidget);
      final mealPos = tester.getTopLeft(mealFinder);
      final recipePos = tester.getTopLeft(recipeFinder);
      final mealFirst = mealPos.dy < recipePos.dy ||
          (mealPos.dy == recipePos.dy && mealPos.dx < recipePos.dx);
      expect(mealFirst, isTrue,
          reason: 'Meal should render before recipe (newer first)');
    });
  });

  group('HomeScreen — md-4 Favorites carousel', () {
    testWidgets('empty favorited_meals does not leak the key', (tester) async {
      _registerFakes(_FakeApiClient(recipes: [_recipe(id: 'r1', name: 'X')]));
      await _pumpHome(tester);
      // zero-regression: no Favorites section rendered at all when both lists
      // empty.
      expect(find.text('Favorites'), findsNothing);
    });

    testWidgets('favorited meal renders in favorites carousel',
        (tester) async {
      _registerFakes(_FakeApiClient(
        recipes: [_recipe(id: 'r1', name: 'X')],
        favoritedMeals: [
          _mealSummary(id: 'm-fav', name: 'Fav Kale'),
        ],
      ));
      await _pumpHome(tester);

      // Section header is present because the merged _favorites is non-empty.
      expect(find.text('Favorites'), findsOneWidget);
      expect(find.text('Fav Kale'), findsOneWidget);
    });
  });
}
