// cmm-3 — sectioned step traversal + navigator boundary rules +
// flat-total progress-bar behavior. cmlp-4 removed the
// RecipeSectionHeader render call; the test that asserted on that
// widget's fields has been deleted.

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/cook_timer_notification_service.dart';
import 'package:palateful/core/services/live_activity_service.dart';
import 'package:palateful/core/services/recipe_cache_service.dart';
import 'package:palateful/core/theme/app_theme.dart';
import 'package:palateful/features/meals/models/meal.dart';
import 'package:palateful/features/meals/services/meal_service.dart';
import 'package:palateful/features/recipes/cook_mode/meal/meal_cook_mode_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'helpers/cook_mode_test_harness.dart';

class _FakeApi extends ApiClient {
  final Map<String, Map<String, dynamic>> recipes;
  _FakeApi(this.recipes);
  @override
  Future<Response> getRecipe(String id, {bool debug = false}) async {
    final data = recipes[id]!;
    return Response(
      data: data,
      requestOptions: RequestOptions(path: '/v1/recipes/$id'),
      statusCode: 200,
    );
  }

  @override
  Future<Response> recordClientError({
    required String errorType,
    required String errorMessage,
    String? area,
    String? operation,
    Map<String, Object?>? extras,
    int? statusCode,
  }) async =>
      Response(
        data: const {'ok': true},
        requestOptions: RequestOptions(path: ''),
        statusCode: 200,
      );
}

class _FakeMealService extends MealService {
  final Meal m;
  _FakeMealService(this.m, ApiClient api) : super(api);
  @override
  Future<Meal> getMeal(String mealId) async => m;
}

Map<String, dynamic> _recipe(String id, String name, int stepCount) => {
      'id': id,
      'name': name,
      'steps': List.generate(
        stepCount,
        (i) => {
          'step_number': i + 1,
          'instruction': 'Step ${i + 1} of $name',
          'timers': const [],
        },
      ),
      'ingredients': const [],
    };

Future<void> _setUp({
  required Meal meal,
  required Map<String, Map<String, dynamic>> recipes,
}) async {
  TestWidgetsFlutterBinding.ensureInitialized();
  if (!dotenv.isInitialized) {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  }
  SharedPreferences.setMockInitialValues({});
  final gi = GetIt.instance;
  final api = _FakeApi(recipes);
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  gi.registerSingleton<ApiClient>(api);
  if (gi.isRegistered<MealService>()) gi.unregister<MealService>();
  gi.registerSingleton<MealService>(_FakeMealService(meal, api));
  if (gi.isRegistered<CookTimerNotificationService>()) {
    gi.unregister<CookTimerNotificationService>();
  }
  gi.registerSingleton<CookTimerNotificationService>(
      RecordingTimerNotifService());
  if (gi.isRegistered<LiveActivityService>()) {
    gi.unregister<LiveActivityService>();
  }
  gi.registerSingleton<LiveActivityService>(LiveActivityService());
  if (gi.isRegistered<RecipeCacheService>()) {
    gi.unregister<RecipeCacheService>();
  }
  gi.registerSingleton<RecipeCacheService>(RecipeCacheService());
}

void _tearDown() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  if (gi.isRegistered<MealService>()) gi.unregister<MealService>();
  if (gi.isRegistered<CookTimerNotificationService>()) {
    gi.unregister<CookTimerNotificationService>();
  }
  if (gi.isRegistered<LiveActivityService>()) {
    gi.unregister<LiveActivityService>();
  }
  if (gi.isRegistered<RecipeCacheService>()) {
    gi.unregister<RecipeCacheService>();
  }
}

Widget _harness(String mealId) {
  final router = GoRouter(routes: [
    GoRoute(path: '/', builder: (_, __) => MealCookModeScreen(mealId: mealId)),
  ]);
  return ProviderScope(
    child: MaterialApp.router(theme: AppTheme.light(), routerConfig: router),
  );
}

Future<void> _pump(WidgetTester tester, String mealId) async {
  tester.view.physicalSize = const Size(1080, 2400);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(() {
    tester.view.resetPhysicalSize();
    tester.view.resetDevicePixelRatio();
  });
  await tester.pumpWidget(_harness(mealId));
  for (var i = 0; i < 20; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  tearDown(_tearDown);

  group('cmm-3 — navigator boundaries + flat-total progress bar', () {
    testWidgets('navigator boundary rules render at indices 7 and 11',
        (tester) async {
      final meal = Meal(
        id: 'meal-2',
        name: 'Salad Night',
        recipeBookId: 'b1',
        createdAt: DateTime(2026),
        updatedAt: DateTime(2026),
        components: const [
          MealComponent(recipeId: 'r1', name: 'Dressing', orderIndex: 0),
          MealComponent(recipeId: 'r2', name: 'Salad', orderIndex: 1),
          MealComponent(
              recipeId: 'r3', name: 'Grilled Chicken', orderIndex: 2),
        ],
      );
      await _setUp(meal: meal, recipes: {
        'r1': _recipe('r1', 'Dressing', 7),
        'r2': _recipe('r2', 'Salad', 4),
        'r3': _recipe('r3', 'Grilled Chicken', 9),
      });
      await _pump(tester, 'meal-2');

      // Boundary index 0 never draws a rule (first pill).
      expect(
        find.byKey(const ValueKey('step_navigator_boundary_0')),
        findsNothing,
      );
      // Boundaries at 7 and 11 each render a rule wrapper.
      expect(
        find.byKey(const ValueKey('step_navigator_boundary_7')),
        findsOneWidget,
      );
      expect(
        find.byKey(const ValueKey('step_navigator_boundary_11')),
        findsOneWidget,
      );
    });

    testWidgets('flat-total progress bar at flat-step 9 of 20 ≈ 50%',
        (tester) async {
      final meal = Meal(
        id: 'meal-progress',
        name: 'Salad Night',
        recipeBookId: 'b1',
        createdAt: DateTime(2026),
        updatedAt: DateTime(2026),
        components: const [
          MealComponent(recipeId: 'r1', name: 'Dressing', orderIndex: 0),
          MealComponent(recipeId: 'r2', name: 'Salad', orderIndex: 1),
          MealComponent(
              recipeId: 'r3', name: 'Grilled Chicken', orderIndex: 2),
        ],
      );
      await _setUp(meal: meal, recipes: {
        'r1': _recipe('r1', 'Dressing', 7),
        'r2': _recipe('r2', 'Salad', 4),
        'r3': _recipe('r3', 'Grilled Chicken', 9),
      });
      await _pump(tester, 'meal-progress');

      // Advance 9 times → flat-step 9 of 20 → progress = 10/20 = 0.5.
      for (var i = 0; i < 9; i++) {
        await tester.tap(find.text('Next'));
        await tester.pump();
      }
      final progress = tester.widget<LinearProgressIndicator>(
        find.byType(LinearProgressIndicator),
      );
      expect(progress.value, closeTo(10 / 20, 1e-9));
    });
  });
}
