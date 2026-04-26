// hmp-4 — Hide components of Meals filter, end-to-end.
//
// Drives the home grid through the filter sheet toggle and asserts the
// grid reflows: component recipes disappear when the toggle is ON; the
// Meal remains; the toggle is a no-op when the grid has no Meals.

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/core/services/shared_state_service.dart';
import 'package:palateful/features/home/home_screen.dart';
import 'package:palateful/features/home/widgets/recipe_card.dart';
import 'package:palateful/features/meals/services/meal_service.dart';
import 'package:palateful/features/meals/widgets/meal_tile.dart';
import 'package:palateful/features/recipes/add_recipe/batch_parser_service.dart';
import 'package:palateful/features/recipe_books/services/recipe_book_service.dart';

Response<dynamic> _ok(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _FakeApi extends ApiClient {
  final List<Map<String, dynamic>> recipes;
  final List<Map<String, dynamic>> meals;

  _FakeApi({this.recipes = const [], this.meals = const []});

  @override
  Future<Response> getRecipeBooks({int limit = 20, int offset = 0}) async =>
      _ok({
        'items': [
          {'id': 'book-1', 'name': 'Dinners'}
        ]
      });

  @override
  Future<Response> getRecipeBook(String id) async =>
      _ok({'id': id, 'name': 'Dinners', 'recipes': recipes});

  @override
  Future<Response> getFavorites() async =>
      _ok({'items': <Map<String, dynamic>>[], 'favorited_meals': <Map<String, dynamic>>[]});

  @override
  Future<Response> listMeals({
    int? limit,
    int offset = 0,
    bool includeArchived = false,
    bool? archived,
    String? scope,
    String? q,
  }) async =>
      _ok({'items': meals, 'total': meals.length});

  @override
  Future<Response> getMealEventsForToday() async =>
      _ok({'items': <Map<String, dynamic>>[], 'total': 0});

  @override
  Future<Response> getRecentlyCookedRecipes({int limit = 5}) async =>
      _ok({'items': <Map<String, dynamic>>[], 'total': 0});
}

void _registerFakes(_FakeApi client) {
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
}) =>
    {
      'id': id,
      'name': name,
      'recipe_book_id': 'book-1',
      'recipe_book_name': 'Dinners',
      'updated_at': '2026-04-01T00:00:00Z',
      'created_at': '2026-04-01T00:00:00Z',
      'tags': <String>[],
    };

Map<String, dynamic> _meal({
  required String id,
  required String name,
  List<String> componentRecipeIds = const [],
}) =>
    {
      'id': id,
      'name': name,
      'recipe_book_id': 'book-1',
      'component_count': componentRecipeIds.length,
      'component_image_urls': <String>[],
      'component_recipe_ids': componentRecipeIds,
      'updated_at': '2026-04-18T00:00:00Z',
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
  await tester.pumpAndSettle();
  await tester.pump(const Duration(milliseconds: 300));
}

/// Story 5: the hide-components toggle moved to HideInMealsChip.
/// Default is now ON, so this helper *toggles* whichever direction
/// the chip is currently in. Tests should call it deliberately based
/// on the assertion they want.
Future<void> _toggleHideInMealsChip(WidgetTester tester) async {
  await tester.tap(find.byKey(const ValueKey('hide_in_meals_chip')));
  await tester.pumpAndSettle();
  await tester.pump(const Duration(milliseconds: 300));
}

Future<void> _applyMealsOnly(WidgetTester tester) async {
  await tester.tap(find.byTooltip('Sort & filter'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('Meals only'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('Apply'));
  await tester.pumpAndSettle();
  await tester.pump(const Duration(milliseconds: 300));
}

void main() {
  setUpAll(() async {
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

  testWidgets('zero Meals — hide chip is visually present but a no-op',
      (tester) async {
    _registerFakes(_FakeApi(
      recipes: [
        _recipe(id: 'r1', name: 'Kale Salad'),
        _recipe(id: 'r2', name: 'Miso Broccoli'),
      ],
    ));
    await _pumpHome(tester);
    // Default is hide=ON but no meals → nothing to hide.
    expect(find.byType(RecipeCard), findsNWidgets(2));
    // Toggling the chip should still leave 2 recipes visible.
    await _toggleHideInMealsChip(tester);
    expect(find.byType(RecipeCard), findsNWidgets(2));
    expect(find.byType(MealTile), findsNothing);
  });

  testWidgets('1 Meal with 2 components — components hidden by default',
      (tester) async {
    _registerFakes(_FakeApi(
      recipes: [
        _recipe(id: 'r1', name: 'Kale Salad'),
        _recipe(id: 'r2', name: 'Lemon Dressing'),
        _recipe(id: 'r3', name: 'Uncombined Recipe'),
      ],
      meals: [
        _meal(
          id: 'm1',
          name: 'Kale Salad Meal',
          componentRecipeIds: ['r1', 'r2'],
        ),
      ],
    ));
    await _pumpHome(tester);
    // Story 5: hide is ON by default → r1 + r2 are hidden from start.
    expect(find.byType(RecipeCard), findsOneWidget);
    expect(find.text('Uncombined Recipe'), findsOneWidget);
    expect(find.byType(MealTile), findsOneWidget);

    // Tap the chip → hide turns OFF → all 3 recipes reappear.
    await _toggleHideInMealsChip(tester);
    expect(find.byType(RecipeCard), findsNWidgets(3));

    // Tap again → hide back ON → r1 + r2 hidden again.
    await _toggleHideInMealsChip(tester);
    expect(find.byType(RecipeCard), findsOneWidget);
    expect(find.text('Uncombined Recipe'), findsOneWidget);
    expect(find.byType(MealTile), findsOneWidget);
    // Meal name still renders on the tile.
    expect(find.text('Kale Salad Meal'), findsWidgets);
  });

  testWidgets('Meals only — hides all recipes, keeps only Meals',
      (tester) async {
    _registerFakes(_FakeApi(
      recipes: [
        _recipe(id: 'r1', name: 'Kale Salad'),
      ],
      meals: [
        _meal(id: 'm1', name: 'Kale Salad Meal'),
      ],
    ));
    await _pumpHome(tester);
    expect(find.byType(RecipeCard), findsOneWidget);
    expect(find.byType(MealTile), findsOneWidget);

    await _applyMealsOnly(tester);

    expect(find.byType(RecipeCard), findsNothing);
    expect(find.byType(MealTile), findsOneWidget);
  });
}
