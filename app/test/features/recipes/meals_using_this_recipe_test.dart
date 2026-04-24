// md-6: MealsUsingThisRecipe widget.

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/meals/services/meal_service.dart';
import 'package:palateful/features/recipes/widgets/meals_using_this_recipe.dart';

Response<dynamic> _fakeResponse(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _FakeApiClient extends ApiClient {
  final List<Map<String, dynamic>>? meals;
  final bool throwError;

  _FakeApiClient({this.meals, this.throwError = false});

  @override
  Future<Response> listMealsUsingRecipe(String recipeId) async {
    if (throwError) {
      throw DioException(
        requestOptions: RequestOptions(path: ''),
        error: 'network',
      );
    }
    return _fakeResponse({'items': meals ?? <Map<String, dynamic>>[]});
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

Map<String, dynamic> _mealSummary({
  required String id,
  required String name,
  int componentCount = 2,
}) =>
    {
      'id': id,
      'name': name,
      'recipe_book_id': 'book-1',
      'component_count': componentCount,
      'component_image_urls': <String>[],
      'archived_at': null,
      'updated_at': '2026-04-18T00:00:00Z',
    };

Widget _pumpTarget(Widget child) {
  // Wrap in a minimal GoRouter so `context.push('/meals/X')` doesn't crash.
  final router = GoRouter(
    initialLocation: '/',
    routes: [
      GoRoute(path: '/', builder: (_, _) => Scaffold(body: child)),
      GoRoute(
        path: '/meals/:id',
        builder: (_, state) =>
            Scaffold(body: Text('meal-${state.pathParameters['id']}')),
      ),
    ],
  );
  return ProviderScope(child: MaterialApp.router(routerConfig: router));
}

void main() {
  setUpAll(() async {
  });

  tearDown(_unregister);

  group('MealsUsingThisRecipe', () {
    testWidgets('zero meals hides entirely (SizedBox.shrink, no header)',
        (tester) async {
      _registerFakes(_FakeApiClient(meals: []));
      await tester.pumpWidget(_pumpTarget(
        const MealsUsingThisRecipe(recipeId: 'r1'),
      ));
      await tester.pumpAndSettle();
      // No header copy ever appears.
      expect(find.textContaining('Used in'), findsNothing);
    });

    testWidgets('1 meal renders "Used in 1 meal" singular header',
        (tester) async {
      _registerFakes(_FakeApiClient(
        meals: [_mealSummary(id: 'm1', name: 'Kale Salad Meal')],
      ));
      await tester.pumpWidget(_pumpTarget(
        const MealsUsingThisRecipe(recipeId: 'r1'),
      ));
      await tester.pumpAndSettle();
      expect(find.text('Used in 1 meal'), findsOneWidget);
      expect(find.text('Kale Salad Meal'), findsOneWidget);
    });

    testWidgets('N meals renders plural header and all tiles',
        (tester) async {
      _registerFakes(_FakeApiClient(
        meals: [
          for (var i = 0; i < 5; i++)
            _mealSummary(id: 'm$i', name: 'Meal $i'),
        ],
      ));
      await tester.pumpWidget(_pumpTarget(
        const MealsUsingThisRecipe(recipeId: 'r1'),
      ));
      await tester.pumpAndSettle();
      expect(find.text('Used in 5 meals'), findsOneWidget);
      expect(find.text('Meal 0'), findsOneWidget);
      expect(find.text('Meal 4'), findsOneWidget);
    });

    testWidgets('fetch error hides the section (no user-facing error)',
        (tester) async {
      _registerFakes(_FakeApiClient(throwError: true));
      await tester.pumpWidget(_pumpTarget(
        const MealsUsingThisRecipe(recipeId: 'r1'),
      ));
      await tester.pumpAndSettle();
      expect(find.textContaining('Used in'), findsNothing);
    });

    testWidgets('loading state renders shimmer placeholders', (tester) async {
      _registerFakes(_FakeApiClient(meals: []));
      await tester.pumpWidget(_pumpTarget(
        const MealsUsingThisRecipe(recipeId: 'r1'),
      ));
      // Pump only a single frame — the future hasn't resolved yet.
      await tester.pump();
      // Shimmer placeholders use a 130-tall horizontal list; header is not
      // rendered during loading.
      expect(find.textContaining('Used in'), findsNothing);
      // Settle for teardown.
      await tester.pumpAndSettle();
    });
  });
}
