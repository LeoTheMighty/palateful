// hmp-5 — Regression sweep: zero-Meal parity, selection + filter
// interaction, a11y smoke, and the epic-wide happy-path walk.
//
// The zero-regression guarantee is load-bearing: if this test ever
// starts rendering MealTile widgets with an empty meals fixture, or
// the filter sheet's two new rows stop being no-ops, we've introduced
// a pre-epic behavioral change that dogfood will flag.

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
import 'package:palateful/features/home/widgets/home_bulk_action_bar.dart';
import 'package:palateful/features/home/widgets/recipe_card.dart';
import 'package:palateful/features/meals/services/meal_service.dart';
import 'package:palateful/features/meals/widgets/create_meal_sheet.dart';
import 'package:palateful/features/meals/widgets/meal_tile.dart';
import 'package:palateful/features/recipes/add_recipe/batch_parser_service.dart';

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

  group('Zero-Meal regression', () {
    testWidgets('empty meal fixture renders no MealTile; grid is recipes only',
        (tester) async {
      _registerFakes(_FakeApi(
        recipes: [
          _recipe(id: 'r1', name: 'Kale Salad'),
          _recipe(id: 'r2', name: 'Miso Broccoli'),
        ],
      ));
      await _pumpHome(tester);

      expect(find.byType(MealTile), findsNothing);
      expect(find.byType(RecipeCard), findsNWidgets(2));
    });

    testWidgets('long-press in zero-Meal still enters selection mode '
        'and bulk bar primary is disabled at 1R', (tester) async {
      _registerFakes(_FakeApi(
        recipes: [_recipe(id: 'r1', name: 'Kale Salad')],
      ));
      await _pumpHome(tester);

      await tester.longPress(find.byType(RecipeCard).first);
      await tester.pumpAndSettle();

      expect(find.byType(HomeBulkActionBar), findsOneWidget);
      // Primary slot renders the teaching-tooltip disabled button.
      expect(find.text('Bulk action unavailable'), findsOneWidget);
    });

    testWidgets('filter sheet\'s two new rows are no-ops with zero Meals',
        (tester) async {
      _registerFakes(_FakeApi(
        recipes: [_recipe(id: 'r1', name: 'Kale Salad')],
      ));
      await _pumpHome(tester);

      await tester.tap(find.byTooltip('Sort & filter'));
      await tester.pumpAndSettle();
      // Hide components toggle flips ON but doesn't change the grid.
      await tester.tap(
        find.byKey(const ValueKey('hide-components-of-meals-toggle')),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Apply'));
      await tester.pumpAndSettle();
      await tester.pump(const Duration(milliseconds: 300));

      expect(find.byType(RecipeCard), findsOneWidget);
      expect(find.byType(MealTile), findsNothing);
    });
  });

  group('Selection + filter interaction', () {
    // NOTE: The filter pill is intentionally hidden while selection
    // mode is active (home_screen's `_buildSearchHeader` is guarded by
    // `!selection.isActive`), so the epic's "flip the filter while in
    // selection mode" scenario is unreachable from the UI. The
    // orthogonal behaviors are covered individually:
    //   - hmp-2's `home_selection_controller_test.dart` exercises
    //     selection persistence across `reconcile()` calls.
    //   - `home_filter_hide_components_test.dart` covers every filter
    //     transition on the grid.
    // This placeholder proves the two domains don't collide: entering
    // selection mode doesn't disturb the filter-pill dot state once
    // the user exits selection.
    testWidgets(
        'active filter remains active after entering + exiting selection',
        (tester) async {
      _registerFakes(_FakeApi(
        recipes: [_recipe(id: 'r1', name: 'Kale Salad')],
        meals: [_meal(id: 'm1', name: 'Kale Salad Meal')],
      ));
      await _pumpHome(tester);

      // Apply "Meals only" filter (no selection active).
      await tester.tap(find.byTooltip('Sort & filter'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Meals only'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Apply'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Apply'));
      await tester.pumpAndSettle();
      await tester.pump(const Duration(milliseconds: 300));
      expect(find.byType(RecipeCard), findsNothing);
      expect(find.byType(MealTile), findsOneWidget);

      // Enter selection mode via the Meal tile, then exit.
      await tester.longPress(find.byType(MealTile).first);
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Exit selection'));
      await tester.pumpAndSettle();

      // Filter is still Meals only after exit.
      expect(find.byType(RecipeCard), findsNothing);
      expect(find.byType(MealTile), findsOneWidget);
    });
  });

  group('A11y semantics smoke', () {
    testWidgets(
        'selection app bar announces "Exit selection" on the X button',
        (tester) async {
      _registerFakes(_FakeApi(
        recipes: [_recipe(id: 'r1', name: 'Kale Salad')],
      ));
      await _pumpHome(tester);

      await tester.longPress(find.byType(RecipeCard).first);
      await tester.pumpAndSettle();
      expect(find.byTooltip('Exit selection'), findsOneWidget);
    });

    testWidgets('bulk bar Archive carries the "Archive selected" label',
        (tester) async {
      _registerFakes(_FakeApi(
        recipes: [_recipe(id: 'r1', name: 'Kale Salad')],
      ));
      await _pumpHome(tester);

      await tester.longPress(find.byType(RecipeCard).first);
      await tester.pumpAndSettle();
      expect(
        find.bySemanticsLabel('Archive selected'),
        findsOneWidget,
      );
    });

    testWidgets(
        'MealTile exposes the "Meal" pill via Semantics (widget-level)',
        (tester) async {
      _registerFakes(_FakeApi(
        recipes: [_recipe(id: 'r1', name: 'Kale Salad')],
        meals: [_meal(id: 'm1', name: 'Kale Salad Meal')],
      ));
      await _pumpHome(tester);
      // MealTile renders — and somewhere in its subtree there's a
      // Semantics widget whose label is exactly "Meal" (the pill).
      expect(find.byType(MealTile), findsOneWidget);
      final mealSemantics = find.descendant(
        of: find.byType(MealTile),
        matching: find.byWidgetPredicate(
          (w) => w is Semantics && w.properties.label == 'Meal',
        ),
      );
      expect(mealSemantics, findsOneWidget);
    });
  });

  group('Epic-wide happy path smoke', () {
    testWidgets(
        'long-press 2 recipes → Create Meal → CreateMealSheet opens '
        'with the selection plumbed through', (tester) async {
      _registerFakes(_FakeApi(
        recipes: [
          _recipe(id: 'r1', name: 'Kale Salad'),
          _recipe(id: 'r2', name: 'Lemon Dressing'),
        ],
      ));
      await _pumpHome(tester);

      await tester.longPress(find.byType(RecipeCard).first);
      await tester.pumpAndSettle();
      await tester.tap(find.byType(RecipeCard).last);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Create Meal'));
      await tester.pumpAndSettle();

      expect(find.byType(CreateMealSheet), findsOneWidget);
      expect(find.text('Kale Salad'), findsWidgets);
      expect(find.text('Lemon Dressing'), findsWidgets);
    });
  });
}
