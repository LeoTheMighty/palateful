// cmmrf-7 — cross-recipe backward-swipe rewind. At local step 0 of a
// later-plan-order recipe, the Prev button + left-25% tap + backward
// swipe all route through _previousStep and flip _activeRecipeId to
// the previously-entered earlier recipe, restoring its last-visited
// step. Backward gesture at step 0 of the first plan-order recipe
// no-ops (unchanged from today).

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
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
  Future<Response> getRecipe(String id, {bool debug = false, List<String>? include}) async => Response(
        data: recipes[id],
        requestOptions: RequestOptions(path: '/v1/recipes/$id'),
        statusCode: 200,
      );
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

Map<String, dynamic> _recipe(String id, String name, int stepCount) =>
    <String, dynamic>{
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
    GoRoute(
      path: '/',
      builder: (_, __) => MealCookModeScreen(mealId: mealId),
    ),
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

Meal _threeCompMeal() => Meal(
      id: 'meal-1',
      name: 'Salad Night',
      recipeBookId: 'b1',
      createdAt: DateTime(2026),
      updatedAt: DateTime(2026),
      components: const [
        MealComponent(recipeId: 'r1', name: 'Dressing', orderIndex: 0),
        MealComponent(recipeId: 'r2', name: 'Salad', orderIndex: 1),
        MealComponent(recipeId: 'r3', name: 'Grilled Chicken', orderIndex: 2),
      ],
    );

Map<String, Map<String, dynamic>> _threeCompRecipes() => {
      'r1': _recipe('r1', 'Dressing', 7),
      'r2': _recipe('r2', 'Salad', 4),
      'r3': _recipe('r3', 'Grilled Chicken', 9),
    };

void main() {
  tearDown(_tearDown);

  group('cmmrf-7 — cross-recipe backward rewind', () {
    testWidgets(
        'advance Dressing to step 3, tap Salad pill, tap Prev → lands on '
        'Dressing step 3', (tester) async {
      await _setUp(meal: _threeCompMeal(), recipes: _threeCompRecipes());
      await _pump(tester, 'meal-1');

      // Advance Dressing 0 → 2 (step 3 of 7).
      for (var i = 0; i < 2; i++) {
        await tester.tap(find.text('Next'));
        await tester.pump();
      }
      expect(find.text('Step 3 of Dressing'), findsOneWidget);

      // Switch to Salad.
      await tester.tap(find.byKey(const Key('toggle_pill_r2')));
      for (var i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }
      expect(find.text('Step 1 of Salad'), findsOneWidget);

      // Tap Prev — at Salad local 0, should cross-rewind to Dressing.
      await tester.tap(find.text('Prev'));
      for (var i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }
      expect(find.text('Step 3 of Dressing'), findsOneWidget);
      expect(find.text('3 / 7'), findsOneWidget);
    });

    testWidgets(
        'backward left-25% tap at Salad step 1 rewinds to Dressing '
        'last-visited', (tester) async {
      await _setUp(meal: _threeCompMeal(), recipes: _threeCompRecipes());
      await _pump(tester, 'meal-1');

      for (var i = 0; i < 2; i++) {
        await tester.tap(find.text('Next'));
        await tester.pump();
      }
      await tester.tap(find.byKey(const Key('toggle_pill_r2')));
      for (var i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }

      // Tap the left 25% of the step-card area. Physical size set by
      // _pump is 1080 wide (devicePixelRatio 1.0); tap at x=50.
      final screenWidth = tester.view.physicalSize.width /
          tester.view.devicePixelRatio;
      // Find the step-card Text and pick a point inside the left 25%.
      // The GestureDetector wraps the whole Expanded region, so any
      // tap inside the step content area is intercepted.
      final stepCardFinder = find.text('Step 1 of Salad');
      final cardRect = tester.getRect(stepCardFinder);
      final tapX = screenWidth * 0.1;
      await tester.tapAt(Offset(tapX, cardRect.center.dy));
      for (var i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }
      expect(find.text('Step 3 of Dressing'), findsOneWidget);
    });

    testWidgets(
        'tap Prev at Dressing step 1 (first plan-order recipe, local 0) '
        'is a no-op', (tester) async {
      await _setUp(meal: _threeCompMeal(), recipes: _threeCompRecipes());
      await _pump(tester, 'meal-1');

      // Prev button should be disabled at initial state.
      final prevFinder = find.text('Prev');
      expect(prevFinder, findsOneWidget);
      // Can't verify disabled from outside the widget easily; tap and
      // assert no state change.
      await tester.tap(prevFinder, warnIfMissed: false);
      for (var i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }
      expect(find.text('Step 1 of Dressing'), findsOneWidget);
    });

    testWidgets(
        'Grilled Chicken pill tap (never-advanced) then Prev rewinds to '
        'Dressing (prior entered)', (tester) async {
      await _setUp(meal: _threeCompMeal(), recipes: _threeCompRecipes());
      await _pump(tester, 'meal-1');

      // User taps Chicken pill without advancing Dressing past step 1.
      await tester.tap(find.byKey(const Key('toggle_pill_r3')));
      for (var i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }
      expect(find.text('Step 1 of Grilled Chicken'), findsOneWidget);

      // Tap Prev at Chicken local 0 → rewinds to prior entered = Dressing
      // (at its last-visited step, which is 0 since we never advanced).
      await tester.tap(find.text('Prev'));
      for (var i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }
      // previousEnteredRecipe('r3', {r1, r3}) returns r1 (Dressing).
      expect(find.text('Step 1 of Dressing'), findsOneWidget);
    });
  });
}
