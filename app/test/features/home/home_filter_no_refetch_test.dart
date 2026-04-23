// pfc-4 — Home filter changes are zero-network.
//
// Regression: `_reapplyFilters` previously called `_loadRecipes()`,
// so every filter flip re-ran every list endpoint. That was a
// perf-2 AC-3 regression. This test drives the home grid through a
// filter change and asserts every list-endpoint counter stays at its
// post-initial-load value.

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/core/services/shared_state_service.dart';
import 'package:palateful/features/home/home_screen.dart';
import 'package:palateful/features/home/widgets/recipe_card.dart';
import 'package:palateful/features/meals/services/meal_service.dart';
import 'package:palateful/features/recipes/add_recipe/batch_parser_service.dart';
import 'package:palateful/features/recipe_books/services/recipe_book_service.dart';

Response<dynamic> _ok(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _CountingApi extends ApiClient {
  final List<Map<String, dynamic>> recipes;
  final List<Map<String, dynamic>> meals;
  int getRecipeBooksCalls = 0;
  int getRecipeBookCalls = 0;
  int getFavoritesCalls = 0;
  int listMealsCalls = 0;

  _CountingApi({this.recipes = const [], this.meals = const []});

  @override
  Future<Response> getRecipeBooks({int limit = 20, int offset = 0}) async {
    getRecipeBooksCalls++;
    return _ok({
      'items': [
        {'id': 'book-1', 'name': 'Dinners'},
      ],
    });
  }

  @override
  Future<Response> getRecipeBook(String id) async {
    getRecipeBookCalls++;
    return _ok({'id': id, 'name': 'Dinners', 'recipes': recipes});
  }

  @override
  Future<Response> getFavorites() async {
    getFavoritesCalls++;
    return _ok({
      'items': <Map<String, dynamic>>[],
      'favorited_meals': <Map<String, dynamic>>[],
    });
  }

  @override
  Future<Response> listMeals({
    int? limit,
    int offset = 0,
    bool includeArchived = false,
    bool? archived,
    String? scope,
    String? q,
  }) async {
    listMealsCalls++;
    return _ok({'items': meals, 'total': meals.length});
  }

  @override
  Future<Response> getMealEventsForToday() async =>
      _ok({'items': <Map<String, dynamic>>[], 'total': 0});

  @override
  Future<Response> getRecentlyCookedRecipes({int limit = 5}) async =>
      _ok({'items': <Map<String, dynamic>>[], 'total': 0});
}

void _registerFakes(_CountingApi client) {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  gi.registerSingleton<ApiClient>(client);
  if (gi.isRegistered<MealService>()) gi.unregister<MealService>();
  gi.registerLazySingleton<MealService>(() => MealService(client));
  if (gi.isRegistered<BatchParserService>()) {
    gi.unregister<BatchParserService>();
  }
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
  if (gi.isRegistered<MealService>()) gi.unregister<MealService>();
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
  String mealType = 'dinner',
}) =>
    {
      'id': id,
      'name': name,
      'recipe_book_id': 'book-1',
      'recipe_book_name': 'Dinners',
      'meal_type': mealType,
      'updated_at': '2026-04-01T00:00:00Z',
      'created_at': '2026-04-01T00:00:00Z',
      'tags': <String>[],
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
  await tester.pumpAndSettle();
  await tester.pump(const Duration(milliseconds: 300));
}

Future<void> _applyMealTypeBreakfast(WidgetTester tester) async {
  await tester.tap(find.byTooltip('Sort & filter'));
  await tester.pumpAndSettle();
  // Meal type section exposes chip buttons keyed by the enum name
  // ('all' / 'breakfast' / 'lunch' / 'dinner' / 'snack').
  await tester.tap(find.text('Breakfast'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('Apply'));
  await tester.pumpAndSettle();
  await tester.pump(const Duration(milliseconds: 300));
}

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  setUp(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, (_) async => null);
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, null);
    _unregister();
  });

  testWidgets(
    'filter change does not re-fetch recipes or meals',
    (tester) async {
      final api = _CountingApi(
        recipes: [
          _recipe(id: 'r1', name: 'Eggs', mealType: 'breakfast'),
          _recipe(id: 'r2', name: 'Steak', mealType: 'dinner'),
          _recipe(id: 'r3', name: 'Pancakes', mealType: 'breakfast'),
        ],
      );
      _registerFakes(api);
      await _pumpHome(tester);

      // Initial load fetched everything once.
      expect(api.getRecipeBooksCalls, 1);
      expect(api.getRecipeBookCalls, 1);
      expect(api.getFavoritesCalls, 1);
      expect(api.listMealsCalls, 1);
      expect(find.byType(RecipeCard), findsNWidgets(3));

      // Change the meal filter to Breakfast. All subsequent call counts
      // must stay pinned — zero-network filter.
      await _applyMealTypeBreakfast(tester);

      expect(api.getRecipeBooksCalls, 1,
          reason: 'filter flip must not re-fetch recipe books');
      expect(api.getRecipeBookCalls, 1,
          reason: 'filter flip must not re-fetch per-book recipes');
      expect(api.getFavoritesCalls, 1,
          reason: 'filter flip must not re-fetch favorites');
      expect(api.listMealsCalls, 1,
          reason: 'filter flip must not re-fetch meals');

      // Grid now shows 2 breakfast recipes — filter applied in-memory.
      expect(find.byType(RecipeCard), findsNWidgets(2));
      expect(find.text('Eggs'), findsOneWidget);
      expect(find.text('Pancakes'), findsOneWidget);
      expect(find.text('Steak'), findsNothing);
    },
  );
}
