// cmm-5 — meal-level timers + component-name label disambiguation.

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
import 'package:palateful/features/recipes/cook_mode/shared/widgets/active_timers_row.dart';
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

Map<String, dynamic> _recipe(
  String id,
  String name, {
  required int stepCount,
}) =>
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

Future<RecordingTimerNotifService> _setUp({
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
  final notif = RecordingTimerNotifService();
  gi.registerSingleton<CookTimerNotificationService>(notif);
  if (gi.isRegistered<LiveActivityService>()) {
    gi.unregister<LiveActivityService>();
  }
  gi.registerSingleton<LiveActivityService>(LiveActivityService());
  if (gi.isRegistered<RecipeCacheService>()) {
    gi.unregister<RecipeCacheService>();
  }
  gi.registerSingleton<RecipeCacheService>(RecipeCacheService());
  return notif;
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

  group('cmm-5 — component-name timer disambiguation', () {
    testWidgets(
        'second "simmer" from a different component → "Salad · simmer"; '
        'first stays unchanged',
        (tester) async {
      final meal = Meal(
        id: 'meal-1',
        name: 'Two Pots',
        recipeBookId: 'b1',
        createdAt: DateTime(2026),
        updatedAt: DateTime(2026),
        components: const [
          MealComponent(recipeId: 'r1', name: 'Dressing', orderIndex: 0),
          MealComponent(recipeId: 'r2', name: 'Salad', orderIndex: 1),
        ],
      );
      final notif = await _setUp(meal: meal, recipes: {
        'r1': _recipe('r1', 'Dressing', stepCount: 2),
        'r2': _recipe('r2', 'Salad', stepCount: 2),
      });
      await _pump(tester, 'meal-1');

      // Start a manual "simmer" timer on the first Dressing step.
      await tester.tap(find.byTooltip('Add a timer'));
      await tester.pumpAndSettle();
      await tester.enterText(
          find.byKey(const Key('manual_timer_minutes')), '5');
      await tester.enterText(
          find.byKey(const Key('manual_timer_label')), 'simmer');
      await tester.tap(find.byKey(const Key('manual_timer_start')));
      for (var i = 0; i < 5; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }
      // First scheduled notification has label "simmer" (no prefix).
      expect(notif.scheduled.last['label'], 'simmer');

      // Advance past Dressing's 2 steps into Salad's range.
      await tester.tap(find.text('Next'));
      await tester.pump();
      await tester.tap(find.text('Next'));
      await tester.pump();

      // Start another "simmer" on Salad — should be disambiguated.
      await tester.tap(find.byTooltip('Add a timer'));
      await tester.pumpAndSettle();
      await tester.enterText(
          find.byKey(const Key('manual_timer_minutes')), '3');
      await tester.enterText(
          find.byKey(const Key('manual_timer_label')), 'simmer');
      await tester.tap(find.byKey(const Key('manual_timer_start')));
      for (var i = 0; i < 5; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }
      // Latest scheduled notification carries the component-prefixed
      // label "Salad · simmer".
      expect(notif.scheduled.last['label'], 'Salad · simmer');
      // The original "simmer" notification scheduled earlier is
      // unchanged (first-come-first-served).
      expect(
        notif.scheduled.where((s) => s['label'] == 'simmer').length,
        1,
      );
    });

    testWidgets(
        'manual timer with empty label defaults to current component name',
        (tester) async {
      final meal = Meal(
        id: 'meal-default',
        name: 'Default Meal',
        recipeBookId: 'b1',
        createdAt: DateTime(2026),
        updatedAt: DateTime(2026),
        components: const [
          MealComponent(recipeId: 'r1', name: 'Dressing', orderIndex: 0),
        ],
      );
      final notif = await _setUp(meal: meal, recipes: {
        'r1': _recipe('r1', 'Dressing', stepCount: 2),
      });
      await _pump(tester, 'meal-default');

      await tester.tap(find.byTooltip('Add a timer'));
      await tester.pumpAndSettle();
      await tester.enterText(
          find.byKey(const Key('manual_timer_minutes')), '5');
      // Clear the label field — sheet's default is "Timer".
      await tester.enterText(
          find.byKey(const Key('manual_timer_label')), '');
      await tester.tap(find.byKey(const Key('manual_timer_start')));
      for (var i = 0; i < 5; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }
      // Empty label → defaults to current component name.
      expect(notif.scheduled.last['label'], 'Dressing');
    });

    testWidgets(
        'two same-component manual timers fall through to " 2" suffix',
        (tester) async {
      final meal = Meal(
        id: 'meal-suffix',
        name: 'Suffix Meal',
        recipeBookId: 'b1',
        createdAt: DateTime(2026),
        updatedAt: DateTime(2026),
        components: const [
          MealComponent(recipeId: 'r1', name: 'Dressing', orderIndex: 0),
        ],
      );
      final notif = await _setUp(meal: meal, recipes: {
        'r1': _recipe('r1', 'Dressing', stepCount: 5),
      });
      await _pump(tester, 'meal-suffix');

      // Start two empty-label timers in a row (same component).
      Future<void> startEmptyLabelTimer(String minutes) async {
        await tester.tap(find.byTooltip('Add a timer'));
        await tester.pumpAndSettle();
        await tester.enterText(
            find.byKey(const Key('manual_timer_minutes')), minutes);
        await tester.enterText(
            find.byKey(const Key('manual_timer_label')), '');
        await tester.tap(find.byKey(const Key('manual_timer_start')));
        for (var i = 0; i < 5; i++) {
          await tester.pump(const Duration(milliseconds: 50));
        }
      }

      await startEmptyLabelTimer('5');
      await startEmptyLabelTimer('3');

      final labels =
          notif.scheduled.map((s) => s['label']).whereType<String>().toList();
      // Two timers; first "Dressing", second "Dressing 2" (legacy
      // suffix path because component is the same).
      expect(labels, contains('Dressing'));
      expect(labels, contains('Dressing 2'));
    });
  });
}
