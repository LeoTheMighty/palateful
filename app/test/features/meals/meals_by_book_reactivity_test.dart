// rmc-1 AC #10 — mealsByBookProvider subscribes to MutationBus and
// invalidates on meal events scoped to its book id.
//
// Driver: ProviderContainer reads `mealsByBookProvider('book-a')`,
// emits a MealCreated scoped to book-a, asserts the provider refetches.
// Also asserts a book-b emission does NOT refetch book-a.

import 'package:dio/dio.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/state/mutation_bus.dart';
import 'package:palateful/features/meals/models/meal.dart';
import 'package:palateful/features/meals/providers/meals_provider.dart';
import 'package:palateful/features/meals/services/meal_service.dart';

Response<dynamic> _ok(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _CountingApi extends ApiClient {
  int listCalls = 0;

  @override
  Future<Response> listMealsInBook(
    String bookId, {
    int limit = 50,
    int offset = 0,
    bool includeArchived = false,
  }) async {
    listCalls++;
    return _ok({
      'items': <Map<String, dynamic>>[
        {
          'id': 'meal-1',
          'name': 'Kale Salad',
          'recipe_book_id': bookId,
          'component_count': 2,
          'updated_at': '2026-04-18T10:00:00Z',
        }
      ],
      'total': 1,
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
  }) async =>
      _ok({'items': [], 'total': 0});
}

void _register(_CountingApi api) {
  final g = GetIt.instance;
  if (g.isRegistered<ApiClient>()) g.unregister<ApiClient>();
  g.registerSingleton<ApiClient>(api);
  if (g.isRegistered<MealService>()) g.unregister<MealService>();
  g.registerLazySingleton<MealService>(() => MealService(api));
}

void _unregister() {
  final g = GetIt.instance;
  if (g.isRegistered<ApiClient>()) g.unregister<ApiClient>();
  if (g.isRegistered<MealService>()) g.unregister<MealService>();
}

Future<void> _pumpMicrotasks() async {
  await Future<void>.delayed(Duration.zero);
}

Map<String, dynamic> _mealJson(String bookId) => {
      'id': 'meal-new',
      'name': 'New Meal',
      'recipe_book_id': bookId,
      'created_at': '2026-04-18T10:00:00Z',
      'updated_at': '2026-04-18T10:00:00Z',
      'is_favorite': false,
      'components': <Map<String, dynamic>>[],
    };

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  late _CountingApi api;
  late ProviderContainer container;

  setUp(() {
    api = _CountingApi();
    _register(api);
    container = ProviderContainer();
  });

  tearDown(() {
    container.dispose();
    _unregister();
  });

  test(
    'MealCreated in book-a invalidates mealsByBookProvider(book-a)',
    () async {
      // Prime — one fetch for the initial read.
      final first = await container.read(
        mealsByBookProvider('book-a').future,
      );
      expect(first, isA<List<MealSummary>>());
      expect(api.listCalls, 1);

      // Keep the provider alive while we emit.
      final sub = container.listen(mealsByBookProvider('book-a'), (_, _) {});
      addTearDown(sub.close);

      emitMutation(MealCreated(
        mealId: 'meal-new',
        meal: _mealJson('book-a'),
        bookId: 'book-a',
      ));
      // Provider listeners run synchronously; invalidation schedules a
      // refetch on the next microtask.
      await _pumpMicrotasks();
      await container.read(mealsByBookProvider('book-a').future);

      expect(api.listCalls, 2);
    },
  );

  test(
    'MealCreated in book-b does NOT invalidate mealsByBookProvider(book-a)',
    () async {
      await container.read(mealsByBookProvider('book-a').future);
      expect(api.listCalls, 1);

      final sub = container.listen(mealsByBookProvider('book-a'), (_, _) {});
      addTearDown(sub.close);

      emitMutation(MealCreated(
        mealId: 'meal-other',
        meal: _mealJson('book-b'),
        bookId: 'book-b',
      ));
      await _pumpMicrotasks();

      // book-a's listCalls must stay at 1.
      expect(api.listCalls, 1);
    },
  );

  test(
    'MealComponentAdded (no bookId) invalidates because list fields may change',
    () async {
      await container.read(mealsByBookProvider('book-a').future);
      expect(api.listCalls, 1);

      final sub = container.listen(mealsByBookProvider('book-a'), (_, _) {});
      addTearDown(sub.close);

      emitMutation(MealComponentAdded(
        mealId: 'meal-1',
        recipeId: 'r-new',
        meal: _mealJson('book-a'),
      ));
      await _pumpMicrotasks();
      await container.read(mealsByBookProvider('book-a').future);

      expect(api.listCalls, 2);
    },
  );

  test('unrelated RecipeCreated does NOT invalidate', () async {
    await container.read(mealsByBookProvider('book-a').future);
    expect(api.listCalls, 1);

    final sub = container.listen(mealsByBookProvider('book-a'), (_, _) {});
    addTearDown(sub.close);

    emitMutation(const RecipeCreated(
      recipeId: 'r-1',
      recipe: {'id': 'r-1'},
      bookId: 'book-a',
    ));
    await _pumpMicrotasks();

    expect(api.listCalls, 1);
  });
}
