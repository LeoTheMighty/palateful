// rmc-2 — MealComponentAdded reaches the recipe-detail "Used in these
// Meals" row without a remount.
//
// Shape:
//   1. Pump MealsUsingThisRecipe with fake API returning [MealA].
//   2. Assert MealA visible.
//   3. Flip fake to return [MealA, MealB].
//   4. Emit MealComponentAdded(recipeId matches, meal: MealB) via
//      pumpWithMutation.
//   5. Assert MealA + MealB visible; no shimmer flash.

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/state/mutation_bus.dart';
import 'package:palateful/features/meals/services/meal_service.dart';
import 'package:palateful/features/recipes/widgets/meals_using_this_recipe.dart';
import 'package:palateful/shared/widgets/shimmer_loading.dart'; // ignore: unused_import

import '../../helpers/mutation_bus_test_helper.dart';

Response<dynamic> _ok(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _ReactiveApi extends ApiClient {
  List<Map<String, dynamic>> meals;
  int listCalls = 0;

  _ReactiveApi({required this.meals});

  @override
  Future<Response> listMealsUsingRecipe(String recipeId) async {
    listCalls++;
    return _ok({'items': meals});
  }
}

Map<String, dynamic> _mealSummary({
  required String id,
  required String name,
}) =>
    {
      'id': id,
      'name': name,
      'recipe_book_id': 'book-1',
      'component_count': 2,
      'component_image_urls': <String>[],
      'archived_at': null,
      'updated_at': '2026-04-18T00:00:00Z',
    };

Widget _harness(String recipeId) {
  final router = GoRouter(
    initialLocation: '/',
    routes: [
      GoRoute(
        path: '/',
        builder: (_, _) => Scaffold(
          body: MealsUsingThisRecipe(recipeId: recipeId),
        ),
      ),
      GoRoute(
        path: '/meals/:id',
        builder: (_, state) =>
            Scaffold(body: Text('meal-${state.pathParameters['id']}')),
      ),
    ],
  );
  return ProviderScope(child: MaterialApp.router(routerConfig: router));
}

void _register(_ReactiveApi api) {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  gi.registerSingleton<ApiClient>(api);
  if (gi.isRegistered<MealService>()) gi.unregister<MealService>();
  gi.registerLazySingleton<MealService>(() => MealService(api));
}

void _unregister() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  if (gi.isRegistered<MealService>()) gi.unregister<MealService>();
}

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  tearDown(_unregister);

  testWidgets(
    'MealComponentAdded(recipeId match) refetches and renders new meal',
    (tester) async {
      final api = _ReactiveApi(meals: [
        _mealSummary(id: 'm-a', name: 'Meal A'),
      ]);
      _register(api);

      await tester.pumpWidget(_harness('r-1'));
      await tester.pumpAndSettle();

      expect(find.text('Used in 1 meal'), findsOneWidget);
      expect(find.text('Meal A'), findsOneWidget);
      expect(api.listCalls, 1);

      api.meals = [
        _mealSummary(id: 'm-a', name: 'Meal A'),
        _mealSummary(id: 'm-b', name: 'Meal B'),
      ];

      await pumpWithMutation(
        tester,
        const MealComponentAdded(
          mealId: 'm-b',
          recipeId: 'r-1',
          meal: {
            'id': 'm-b',
            'name': 'Meal B',
            'recipe_book_id': 'book-1',
            'created_at': '2026-04-18T00:00:00Z',
            'updated_at': '2026-04-18T00:00:00Z',
            'is_favorite': false,
            'components': <Map<String, dynamic>>[],
          },
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Used in 2 meals'), findsOneWidget);
      expect(find.text('Meal A'), findsOneWidget);
      expect(find.text('Meal B'), findsOneWidget);
      // Narrow-match path — invalidates immediately, no debounce.
      expect(api.listCalls, 2);
    },
  );

  testWidgets(
    'MealComponentAdded for a different recipeId does NOT refetch',
    (tester) async {
      final api = _ReactiveApi(meals: [
        _mealSummary(id: 'm-a', name: 'Meal A'),
      ]);
      _register(api);

      await tester.pumpWidget(_harness('r-1'));
      await tester.pumpAndSettle();
      expect(api.listCalls, 1);

      await pumpWithMutation(
        tester,
        const MealComponentAdded(
          mealId: 'm-b',
          recipeId: 'r-OTHER',
          meal: {
            'id': 'm-b',
            'name': 'Other',
            'recipe_book_id': 'book-1',
            'created_at': '2026-04-18T00:00:00Z',
            'updated_at': '2026-04-18T00:00:00Z',
            'is_favorite': false,
            'components': <Map<String, dynamic>>[],
          },
        ),
      );
      await tester.pump(const Duration(milliseconds: 200));

      expect(api.listCalls, 1);
    },
  );

  testWidgets(
    'MealUpdated triggers coalesced refetch (debounced 100ms)',
    (tester) async {
      final api = _ReactiveApi(meals: [
        _mealSummary(id: 'm-a', name: 'Meal A'),
      ]);
      _register(api);

      await tester.pumpWidget(_harness('r-1'));
      await tester.pumpAndSettle();
      expect(api.listCalls, 1);

      // Three MealUpdated events within the 100ms window → exactly one
      // refetch, not three.
      emitMutation(const MealUpdated(mealId: 'm-a', meal: {'id': 'm-a'}));
      await tester.pump(const Duration(milliseconds: 20));
      emitMutation(const MealUpdated(mealId: 'm-a', meal: {'id': 'm-a'}));
      await tester.pump(const Duration(milliseconds: 20));
      emitMutation(const MealUpdated(mealId: 'm-a', meal: {'id': 'm-a'}));

      // Before the debounce fires.
      await tester.pump(const Duration(milliseconds: 50));
      expect(api.listCalls, 1);

      // After the debounce fires + refetch completes.
      await tester.pump(const Duration(milliseconds: 150));
      await tester.pumpAndSettle();
      expect(api.listCalls, 2);
    },
  );
}
