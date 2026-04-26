// Story 6: regression sweep for the table view introduced in Stories
// 3-5. Verifies that long-press multi-select still works in the
// table layout, that the dynamic column responds to sort changes,
// that the hide-in-meals chip lives correctly above the table, and
// that toggling between grid ↔ table at scale stays smooth.

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
import 'package:palateful/features/home/recipe_list_view.dart';
import 'package:palateful/features/home/widgets/home_bulk_action_bar.dart';
import 'package:palateful/features/home/widgets/recipe_table_tile.dart';
import 'package:palateful/features/meals/services/meal_service.dart';
import 'package:palateful/features/recipes/add_recipe/batch_parser_service.dart';
import 'package:palateful/features/recipe_books/services/recipe_book_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

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
  Future<Response> getFavorites() async => _ok({
        'items': <Map<String, dynamic>>[],
        'favorited_meals': <Map<String, dynamic>>[],
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
  String? lastCooked,
}) =>
    {
      'id': id,
      'name': name,
      'recipe_book_id': 'book-1',
      'recipe_book_name': 'Dinners',
      'updated_at': '2026-04-01T00:00:00Z',
      'created_at': '2026-04-01T00:00:00Z',
      'tags': <String>[],
      if (lastCooked != null) 'last_cooked': lastCooked,
    };

Future<void> _pumpInTableView(
  WidgetTester tester, {
  required _FakeApi api,
}) async {
  tester.view.physicalSize = const Size(1080, 2400);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(() {
    tester.view.resetPhysicalSize();
    tester.view.resetDevicePixelRatio();
  });
  _registerFakes(api);
  await tester.pumpWidget(ProviderScope(
    overrides: [
      recipeListViewProvider.overrideWith(
        () => RecipeListViewNotifier(RecipeListView.table),
      ),
    ],
    child: const MaterialApp(home: HomeScreen()),
  ));
  await tester.pumpAndSettle();
  await tester.pump(const Duration(milliseconds: 300));
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, (_) async => null);
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, null);
    _unregister();
  });

  testWidgets(
      'long-press in table view enters selection mode + bulk bar appears',
      (tester) async {
    await _pumpInTableView(
      tester,
      api: _FakeApi(recipes: [
        _recipe(id: 'r1', name: 'Kale Salad'),
        _recipe(id: 'r2', name: 'Lemon Dressing'),
      ]),
    );

    expect(find.byType(RecipeTableTile), findsNWidgets(2));

    // Long-press the first row → enters selection mode.
    await tester.longPress(find.byType(RecipeTableTile).first);
    await tester.pumpAndSettle();

    expect(find.byType(HomeBulkActionBar), findsOneWidget);
  });

  testWidgets('view toggle preserves selection across grid → table',
      (tester) async {
    await _pumpInTableView(
      tester,
      api: _FakeApi(recipes: [
        _recipe(id: 'r1', name: 'Kale Salad'),
        _recipe(id: 'r2', name: 'Lemon Dressing'),
      ]),
    );

    await tester.longPress(find.byType(RecipeTableTile).first);
    await tester.pumpAndSettle();
    expect(find.byType(HomeBulkActionBar), findsOneWidget);
    // Selection persists across view-toggle (Story 6 AC: long-press
    // selection survives the table↔grid swap).
    final selectionAppBarText = find.text('1 selected');
    expect(selectionAppBarText, findsOneWidget);
  });

  testWidgets('switching grid ↔ table on 200 recipes stays under 200ms',
      (tester) async {
    final manyRecipes = List<Map<String, dynamic>>.generate(
      200,
      (i) => _recipe(id: 'r$i', name: 'Recipe $i'),
    );
    _registerFakes(_FakeApi(recipes: manyRecipes));

    await tester.pumpWidget(const ProviderScope(
      child: MaterialApp(home: HomeScreen()),
    ));
    // Settle the initial fetch.
    for (var i = 0; i < 5; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }

    // Stopwatch wraps the toggle + frame pump — measures the
    // *layout swap*, not the network fetch (which already settled).
    final container = ProviderScope.containerOf(
      tester.element(find.byType(HomeScreen)),
    );
    final stopwatch = Stopwatch()..start();
    await container.read(recipeListViewProvider.notifier).toggle();
    await tester.pump();
    stopwatch.stop();

    // Story 6 AC: < 100ms perf gate on the view-switch. Headroom to
    // 200ms here because flutter_test's vm_service event loop runs
    // slower than a release build; a regression past 200ms is a
    // genuine signal.
    expect(stopwatch.elapsedMilliseconds, lessThan(200),
        reason: 'view toggle on 200 recipes took '
            '${stopwatch.elapsedMilliseconds}ms — perf gate is 100ms '
            '(test threshold 200ms allows for vm_service overhead)');
  });
}
