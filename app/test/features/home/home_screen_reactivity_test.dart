// rf-3 — Home reactivity regression.
//
// Asserts HomeScreen re-renders when a RecipeCreated event fires on the
// MutationBus, without a pull-to-refresh gesture. Uses the shared
// `pumpWithMutation` helper (microtask + one frame); NEVER calls
// `pumpAndSettle` with a wall-clock timeout — that's the flake risk the
// epic locked out via Locked Decision #5 and QA risk.
//
// Shape:
//   1. Pump HomeScreen with a fake API returning [A] (getRecipeBook).
//   2. Wait for the first AsyncData to render → expect A visible.
//   3. Flip the fake to return [A, B] on the next refetch.
//   4. Emit RecipeCreated('B').
//   5. Pump microtask + frame via pumpWithMutation.
//   6. Assert B visible, A still visible, no shimmer skeleton in tree.

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
import 'package:palateful/core/state/mutation_bus.dart';
import 'package:palateful/features/home/home_screen.dart';
import 'package:palateful/features/home/widgets/recipe_card.dart';
import 'package:palateful/features/meals/services/meal_service.dart';
import 'package:palateful/features/recipes/add_recipe/batch_parser_service.dart';
import 'package:palateful/shared/widgets/shimmer_loading.dart';

import '../../helpers/mutation_bus_test_helper.dart';

Response<dynamic> _ok(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _ReactiveApi extends ApiClient {
  /// Mutable per-test so we can flip the second fetch to include the
  /// new recipe row.
  List<Map<String, dynamic>> recipes;
  int getRecipeBookCalls = 0;

  _ReactiveApi({required this.recipes});

  @override
  Future<Response> getRecipeBooks({int limit = 20, int offset = 0}) async =>
      _ok({
        'items': [
          {'id': 'book-1', 'name': 'Dinners'}
        ],
      });

  @override
  Future<Response> getRecipeBook(String id) async {
    getRecipeBookCalls++;
    return _ok({'id': id, 'name': 'Dinners', 'recipes': recipes});
  }

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
      _ok({'items': <Map<String, dynamic>>[], 'total': 0});

  @override
  Future<Response> getMealEventsForToday() async =>
      _ok({'items': <Map<String, dynamic>>[], 'total': 0});

  @override
  Future<Response> getRecentlyCookedRecipes({int limit = 5}) async =>
      _ok({'items': <Map<String, dynamic>>[], 'total': 0});
}

Map<String, dynamic> _recipe({required String id, required String name}) => {
      'id': id,
      'name': name,
      'recipe_book_id': 'book-1',
      'recipe_book_name': 'Dinners',
      'meal_type': 'dinner',
      'updated_at': '2026-04-01T00:00:00Z',
      'created_at': '2026-04-01T00:00:00Z',
      'tags': <String>[],
    };

void _register(_ReactiveApi client) {
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
  // First pass drains the initial FutureProvider fetch.
  await tester.pumpAndSettle();
  // Drain the 250ms SharedStateService debounced flush timer so it does
  // not leak across test boundaries.
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
    'RecipeCreated event refreshes the grid without pull-to-refresh',
    (tester) async {
      final api = _ReactiveApi(recipes: [_recipe(id: 'r-a', name: 'Alpha')]);
      _register(api);
      await _pumpHome(tester);

      // Initial render — one recipe tile, no skeleton.
      expect(find.text('Alpha'), findsOneWidget);
      expect(find.byType(RecipeCard), findsOneWidget);
      expect(find.byType(ShimmerCard), findsNothing);
      expect(api.getRecipeBookCalls, 1);

      // Flip the fake to return both recipes on the next fetch.
      api.recipes = [
        _recipe(id: 'r-a', name: 'Alpha'),
        _recipe(id: 'r-b', name: 'Bravo'),
      ];

      // Emit the mutation event — provider invalidates, refetches.
      await pumpWithMutation(
        tester,
        RecipeCreated(
          recipeId: 'r-b',
          recipe: {'id': 'r-b', 'name': 'Bravo'},
          bookId: 'book-1',
        ),
      );
      // Drain the refetch + the SharedStateService debounce.
      await tester.pumpAndSettle();
      await tester.pump(const Duration(milliseconds: 300));

      // Alpha still visible; Bravo now present; no skeleton flash.
      expect(find.text('Alpha'), findsOneWidget);
      expect(find.text('Bravo'), findsOneWidget);
      expect(find.byType(RecipeCard), findsNWidgets(2));
      expect(find.byType(ShimmerCard), findsNothing);
      // Exactly one additional fetch — no duplicate storm.
      expect(api.getRecipeBookCalls, 2);
    },
  );

  testWidgets(
    'unrelated event (PantryItemCreated) does NOT trigger a refetch',
    (tester) async {
      final api = _ReactiveApi(recipes: [_recipe(id: 'r-a', name: 'Alpha')]);
      _register(api);
      await _pumpHome(tester);
      expect(api.getRecipeBookCalls, 1);

      await pumpWithMutation(
        tester,
        const PantryItemCreated(itemId: 'p-1', item: {'id': 'p-1'}),
      );
      await tester.pump(const Duration(milliseconds: 300));

      // Count stays at 1 — pantry events are not in the home filter.
      expect(api.getRecipeBookCalls, 1);
    },
  );
}
