// cmmrf-3 — RecipeToggleBar rendering + interaction. Focuses on pill
// copy, active-state swap, completed checkmark, load-failed disabled
// style, single-component hide, tap-to-switch state isolation, and
// Dynamic Type 1.5x overflow behavior.

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
import 'package:palateful/features/recipes/cook_mode/meal/widgets/recipe_toggle_bar.dart';
import 'package:palateful/features/recipes/cook_mode/shared/cook_plan.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'helpers/cook_mode_test_harness.dart';

class _FakeApi extends ApiClient {
  final Map<String, Map<String, dynamic>> recipes;
  final Set<String> failingRecipeIds;
  _FakeApi(this.recipes, {this.failingRecipeIds = const {}});
  @override
  Future<Response> getRecipe(String id, {bool debug = false, List<String>? include}) async {
    if (failingRecipeIds.contains(id)) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/recipes/$id'),
        type: DioExceptionType.badResponse,
        response: Response(
          requestOptions: RequestOptions(path: '/v1/recipes/$id'),
          statusCode: 500,
        ),
      );
    }
    return Response(
      data: recipes[id],
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
  Set<String> failingRecipeIds = const {},
}) async {
  TestWidgetsFlutterBinding.ensureInitialized();
  SharedPreferences.setMockInitialValues({});
  final gi = GetIt.instance;
  final api = _FakeApi(recipes, failingRecipeIds: failingRecipeIds);
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

// Each toggle pill now splits its label into two Text widgets — the
// recipe name (which ellipsizes under squeeze) and the position
// suffix (which must never truncate). Tests that want to assert pill
// copy check for both pieces inside the pill.
void _expectPillLabel(String pillKey, String name, String position) {
  final pill = find.byKey(Key(pillKey));
  expect(pill, findsOneWidget);
  expect(find.descendant(of: pill, matching: find.text(name)),
      findsOneWidget);
  expect(find.descendant(of: pill, matching: find.text(position)),
      findsOneWidget);
}

void main() {
  tearDown(_tearDown);

  group('cmmrf-3 — recipe toggle bar', () {
    testWidgets('3-component meal renders 3 pills with correct copy',
        (tester) async {
      await _setUp(meal: _threeCompMeal(), recipes: _threeCompRecipes());
      await _pump(tester, 'meal-1');

      expect(find.byType(RecipeToggleBar), findsOneWidget);
      _expectPillLabel('toggle_pill_r1', 'Dressing', '1/7');
      _expectPillLabel('toggle_pill_r2', 'Salad', '1/4');
      _expectPillLabel('toggle_pill_r3', 'Grilled Chicken', '1/9');
    });

    testWidgets('single-component meal hides the toggle bar entirely',
        (tester) async {
      final meal = Meal(
        id: 'meal-solo',
        name: 'Solo',
        recipeBookId: 'b1',
        createdAt: DateTime(2026),
        updatedAt: DateTime(2026),
        components: const [
          MealComponent(recipeId: 'r1', name: 'Dressing', orderIndex: 0),
        ],
      );
      await _setUp(meal: meal, recipes: {
        'r1': _recipe('r1', 'Dressing', 7),
      });
      await _pump(tester, 'meal-solo');

      // Widget is present but renders SizedBox.shrink for the single-
      // component case; the pill for Dressing is NOT in the tree.
      expect(find.byKey(const Key('toggle_pill_r1')), findsNothing);
      expect(find.byType(RecipeToggleBar), findsOneWidget);
    });

    testWidgets('tap-to-switch updates active pill + step card',
        (tester) async {
      await _setUp(meal: _threeCompMeal(), recipes: _threeCompRecipes());
      await _pump(tester, 'meal-1');

      // Initial: Dressing step 1.
      expect(find.text('Step 1 of Dressing'), findsOneWidget);

      await tester.tap(find.byKey(const Key('toggle_pill_r2')));
      for (var i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }
      expect(find.text('Step 1 of Salad'), findsOneWidget);
      _expectPillLabel('toggle_pill_r2', 'Salad', '1/4');
    });

    testWidgets(
        'state isolation: advance Dressing to step 3, tap Salad pill → '
        'Salad starts fresh; tap Dressing pill → Dressing at step 3',
        (tester) async {
      await _setUp(meal: _threeCompMeal(), recipes: _threeCompRecipes());
      await _pump(tester, 'meal-1');

      // Advance Dressing 0 → 2 (3rd step).
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

      // Advance Salad once.
      await tester.tap(find.text('Next'));
      await tester.pump();
      expect(find.text('Step 2 of Salad'), findsOneWidget);

      // Switch back to Dressing — step state preserved at 3.
      await tester.tap(find.byKey(const Key('toggle_pill_r1')));
      for (var i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }
      expect(find.text('Step 3 of Dressing'), findsOneWidget);
    });

    testWidgets('tap-to-not-yet-entered pill enters that recipe at step 1',
        (tester) async {
      await _setUp(meal: _threeCompMeal(), recipes: _threeCompRecipes());
      await _pump(tester, 'meal-1');

      await tester.tap(find.byKey(const Key('toggle_pill_r3')));
      for (var i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }
      expect(find.text('Step 1 of Grilled Chicken'), findsOneWidget);
      _expectPillLabel('toggle_pill_r3', 'Grilled Chicken', '1/9');
    });

    testWidgets('load-failed pill renders disabled with ellipsis suffix',
        (tester) async {
      await _setUp(
        meal: _threeCompMeal(),
        recipes: {
          'r1': _recipe('r1', 'Dressing', 7),
          'r2': _recipe('r2', 'Salad', 4),
        },
        failingRecipeIds: const {'r3'},
      );
      await _pump(tester, 'meal-1');

      // Load-failed pill shows name + ellipsis, no step counter.
      _expectPillLabel('toggle_pill_r3', 'Grilled Chicken', '…');
      // Healthy pills still render normally.
      _expectPillLabel('toggle_pill_r1', 'Dressing', '1/7');
      _expectPillLabel('toggle_pill_r2', 'Salad', '1/4');
    });

    testWidgets('tapping a load-failed pill is a no-op (no active switch)',
        (tester) async {
      await _setUp(
        meal: _threeCompMeal(),
        recipes: {
          'r1': _recipe('r1', 'Dressing', 7),
          'r2': _recipe('r2', 'Salad', 4),
        },
        failingRecipeIds: const {'r3'},
      );
      await _pump(tester, 'meal-1');

      expect(find.text('Step 1 of Dressing'), findsOneWidget);
      // `warnIfMissed: false` — by design the load-failed pill has no
      // GestureDetector, so the tap lands on the text-span underneath
      // and produces no state change. Behavior-level assertion below.
      await tester.tap(
        find.byKey(const Key('toggle_pill_r3')),
        warnIfMissed: false,
      );
      for (var i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }
      // Still on Dressing — the failed-component pill tap was swallowed.
      expect(find.text('Step 1 of Dressing'), findsOneWidget);
    });
  });

  group('cmmrf-3 — ComponentSummary binding', () {
    testWidgets(
        'pill label tracks the active recipe\'s current step as user '
        'advances within that recipe', (tester) async {
      await _setUp(meal: _threeCompMeal(), recipes: _threeCompRecipes());
      await _pump(tester, 'meal-1');

      _expectPillLabel('toggle_pill_r1', 'Dressing', '1/7');
      await tester.tap(find.text('Next'));
      await tester.pump();
      _expectPillLabel('toggle_pill_r1', 'Dressing', '2/7');
    });

    testWidgets('Dynamic Type 1.5x does not cause RenderFlex overflow',
        (tester) async {
      await _setUp(meal: _threeCompMeal(), recipes: _threeCompRecipes());
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });
      await tester.pumpWidget(
        MediaQuery(
          data: const MediaQueryData(textScaler: TextScaler.linear(1.5)),
          child: _harness('meal-1'),
        ),
      );
      for (var i = 0; i < 20; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }

      // No overflow exceptions propagate into tester.takeException().
      expect(tester.takeException(), isNull);
      expect(find.byType(RecipeToggleBar), findsOneWidget);
    });
  });

  group('cmmrf-3 — ComponentSummary factory covers isComplete', () {
    test('summaryFor flags isComplete when the last local step is marked',
        () {
      final meal = Meal(
        id: 'm1',
        name: 'M',
        recipeBookId: 'b1',
        createdAt: DateTime(2026),
        updatedAt: DateTime(2026),
        components: const [
          MealComponent(recipeId: 'r1', name: 'A', orderIndex: 0),
          MealComponent(recipeId: 'r2', name: 'B', orderIndex: 1),
        ],
      );
      final plan = CookPlan.fromMeal(meal, [
        _recipe('r1', 'A', 2),
        _recipe('r2', 'B', 3),
      ]);
      expect(
        plan
            .summaryFor('r1', const {'r1': 1, 'r2': 0}, {
              'r1': {0, 1},
            })
            .isComplete,
        isTrue,
      );
      expect(
        plan
            .summaryFor('r2', const {'r1': 1, 'r2': 1}, {
              'r2': {0, 1},
            })
            .isComplete,
        isFalse,
      );
    });
  });
}
