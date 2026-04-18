// md-7: Archive view includes Meals alongside recipes.
//
// Key invariants:
//   * Zero-Meal regression: when the meal service returns [], the archive
//     list looks identical to pre-epic.
//   * Merged list is sorted by `archived_at DESC` across both types.
//   * Restoring a meal hits `POST /v1/meals/{id}/restore` via MealService.

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/meals/services/meal_service.dart';
import 'package:palateful/features/recipes/archived_recipes_screen.dart';

Response<dynamic> _fakeResponse(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _FakeApiClient extends ApiClient {
  final List<Map<String, dynamic>> archivedRecipes;
  final List<Map<String, dynamic>> archivedMeals;
  int restoreCallCount = 0;
  String? lastRestoredMealId;

  _FakeApiClient({
    this.archivedRecipes = const [],
    this.archivedMeals = const [],
  });

  @override
  Future<Response> getArchivedRecipes() async =>
      _fakeResponse({'items': archivedRecipes});

  @override
  Future<Response> listMeals({
    int? limit,
    int offset = 0,
    bool includeArchived = false,
    bool? archived,
    String? scope,
  }) async {
    // Foundation passes includeArchived:true; md-3 accepts archived:true too.
    return _fakeResponse(
        {'items': archivedMeals, 'total': archivedMeals.length});
  }

  @override
  Future<Response> restoreMeal(String id) async {
    restoreCallCount += 1;
    lastRestoredMealId = id;
    return _fakeResponse({'success': true});
  }
}

void _registerFakes(_FakeApiClient client) {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  gi.registerSingleton<ApiClient>(client);
  if (gi.isRegistered<MealService>()) gi.unregister<MealService>();
  gi.registerLazySingleton<MealService>(() => MealService(client));
}

void _unregister() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  if (gi.isRegistered<MealService>()) gi.unregister<MealService>();
}

Map<String, dynamic> _recipe({
  required String id,
  required String name,
  required String archivedAt,
}) =>
    {
      'id': id,
      'name': name,
      'archived_at': archivedAt,
    };

Map<String, dynamic> _meal({
  required String id,
  required String name,
  required String archivedAt,
  int componentCount = 2,
}) =>
    {
      'id': id,
      'name': name,
      'recipe_book_id': 'book-1',
      'component_count': componentCount,
      'component_image_urls': <String>[],
      'archived_at': archivedAt,
      'updated_at': archivedAt,
    };

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  tearDown(_unregister);

  group('ArchivedRecipesScreen — md-7 Meals', () {
    testWidgets('zero-Meal fixture renders only recipes (regression)',
        (tester) async {
      _registerFakes(_FakeApiClient(
        archivedRecipes: [
          _recipe(
            id: 'r1',
            name: 'Grandma Pasta',
            archivedAt: '2026-03-15T10:00:00Z',
          ),
        ],
      ));
      await tester.pumpWidget(
          const MaterialApp(home: ArchivedRecipesScreen()));
      await tester.pumpAndSettle();

      expect(find.text('Grandma Pasta'), findsOneWidget);
      // No meal rows — zero-Meal regression.
      expect(find.textContaining('recipes'), findsNothing);
    });

    testWidgets('mixed archive sorts by archived_at DESC', (tester) async {
      _registerFakes(_FakeApiClient(
        archivedRecipes: [
          _recipe(
            id: 'r-oldest',
            name: 'Old Recipe',
            archivedAt: '2026-01-01T00:00:00Z',
          ),
        ],
        archivedMeals: [
          _meal(
            id: 'm-newest',
            name: 'Newest Meal',
            archivedAt: '2026-05-01T00:00:00Z',
          ),
        ],
      ));
      await tester.pumpWidget(
          const MaterialApp(home: ArchivedRecipesScreen()));
      await tester.pumpAndSettle();

      final mealPos = tester.getTopLeft(find.text('Newest Meal'));
      final recipePos = tester.getTopLeft(find.text('Old Recipe'));
      expect(mealPos.dy < recipePos.dy, isTrue,
          reason: 'Newer-archived Meal should render above older recipe');
    });

    testWidgets('restore Meal hits POST /v1/meals/{id}/restore',
        (tester) async {
      final client = _FakeApiClient(
        archivedMeals: [
          _meal(
            id: 'meal-123',
            name: 'Archived Meal',
            archivedAt: '2026-04-18T00:00:00Z',
          ),
        ],
      );
      _registerFakes(client);
      await tester.pumpWidget(
          const MaterialApp(home: ArchivedRecipesScreen()));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Restore').first);
      await tester.pumpAndSettle();
      expect(client.restoreCallCount, equals(1));
      expect(client.lastRestoredMealId, equals('meal-123'));
      // The restored meal is optimistically removed from the list.
      expect(find.text('Archived Meal'), findsNothing);
    });
  });
}
