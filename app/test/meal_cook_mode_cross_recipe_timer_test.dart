// cmmrf-6 — cross-recipe timer completion: source-recipe pulse +
// recipe-name prefix on the active-timers chip + snackbar. V1-
// restored timers (no sourceRecipeId) render prefixless.

import 'dart:convert';

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
import 'package:palateful/features/recipes/cook_mode/services/cook_session_persister.dart';
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

Future<void> _startManualTimer(
  WidgetTester tester, {
  required String minutes,
  required String label,
}) async {
  await tester.tap(find.byTooltip('Add a timer'));
  await tester.pumpAndSettle();
  await tester.enterText(find.byKey(const Key('manual_timer_minutes')), minutes);
  await tester.enterText(find.byKey(const Key('manual_timer_label')), label);
  await tester.tap(find.byKey(const Key('manual_timer_start')));
  for (var i = 0; i < 5; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}

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

Meal _twoCompMeal() => Meal(
      id: 'meal-1',
      name: 'Salad Night',
      recipeBookId: 'b1',
      createdAt: DateTime(2026),
      updatedAt: DateTime(2026),
      components: const [
        MealComponent(recipeId: 'r1', name: 'Dressing', orderIndex: 0),
        MealComponent(recipeId: 'r2', name: 'Salad', orderIndex: 1),
      ],
    );

Map<String, Map<String, dynamic>> _twoCompRecipes() => {
      'r1': _recipe('r1', 'Dressing', 3),
      'r2': _recipe('r2', 'Salad', 3),
    };

void main() {
  tearDown(_tearDown);

  group('cmmrf-6 — timer chip prefix + cross-recipe pulse', () {
    testWidgets(
        'chip reads `Dressing · MM:SS` when Dressing timer runs while '
        'user is on Salad', (tester) async {
      await _setUp(meal: _twoCompMeal(), recipes: _twoCompRecipes());
      await _pump(tester, 'meal-1');

      await _startManualTimer(tester, minutes: '5', label: 'rest');

      // Switch to Salad.
      await tester.tap(find.byKey(const Key('toggle_pill_r2')));
      for (var i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }

      // Chip in the top active-timers row reads `Dressing · …`.
      expect(find.textContaining('Dressing · '), findsAtLeast(1));
    });
  });

  group('cmmrf-6 — v1-restored timer fallback', () {
    testWidgets(
        'chip renders prefixless when sourceRecipeId is null '
        '(v1-restored timer)', (tester) async {
      await _setUp(meal: _twoCompMeal(), recipes: _twoCompRecipes());
      // Prime a v1 meal payload with a timer payload that lacks
      // source_recipe_id (v1 wire shape).
      final prefs = await SharedPreferences.getInstance();
      final deadline =
          DateTime.now().add(const Duration(minutes: 5)).millisecondsSinceEpoch;
      final v1Payload = {
        'schema_version': 1,
        'target_kind': 'meal',
        'target_id': 'meal-1',
        'started_at_ms': DateTime.now().millisecondsSinceEpoch - 60000,
        'cumulative_elapsed_ms': 60000,
        'current_step': 0,
        'completed_steps': const [],
        'checked_ingredients': const [],
        'active_timers': [
          {
            'label': 'orphan',
            'deadline_ms': deadline,
            'total_duration_s': 300,
            'source': 'extracted',
          },
        ],
        'updated_at_ms': DateTime.now().millisecondsSinceEpoch,
      };
      await prefs.setString(
        CookSessionKey.forMeal('meal-1'),
        jsonEncode(v1Payload),
      );

      await _pump(tester, 'meal-1');
      // Resume the session.
      await tester.tap(find.text('Resume'));
      for (var i = 0; i < 10; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }

      // Chip should NOT have a recipe prefix — v1-restored timer has
      // no `sourceRecipeId`. We assert the chip renders and find no
      // leading "Dressing · " text on a timer label.
      expect(find.textContaining(' · '), findsNothing,
          reason:
              'v1-restored timer chip should render prefixless (no " · " in label)');
    });
  });
}
