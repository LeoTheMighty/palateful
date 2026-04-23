// cmm-7 — meal cook resume gate + restoration + meal-version drift.

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
  Future<Response> getRecipe(String id, {bool debug = false}) async => Response(
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

Map<String, dynamic> _recipe(String id, String name, int stepCount,
        {int ingredientCount = 0}) =>
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
      'ingredients': List.generate(
        ingredientCount,
        (i) => {
          'ingredient': {'canonical_name': 'Ing $i $name'},
          'quantity_display': '1',
          'unit_display': 'cup',
        },
      ),
    };

Future<void> _setUp({
  required Meal meal,
  required Map<String, Map<String, dynamic>> recipes,
}) async {
  TestWidgetsFlutterBinding.ensureInitialized();
  if (!dotenv.isInitialized) {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  }
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
    GoRoute(path: '/', builder: (_, _) => MealCookModeScreen(mealId: mealId)),
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
  for (var i = 0; i < 25; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}

// cmmrf-2 — tests feed flat-step inputs for clarity; this helper
// translates them to v2 per-recipe maps against the fixed [7, 4, 9]
// test plan layout. Over-large inputs (drift tests) are NOT clamped
// here — they pass through to _applyRestoredState so the clamp+
// snackbar branch fires.
CookSessionState _seed({
  required String mealId,
  int currentStep = 5,
  List<int> completed = const [0, 1, 2, 3, 4],
  List<String> checkedIngredients = const ['0:0', '0:1'],
  List<SavedTimerState> timers = const [],
  int cumulativeElapsedMs = 300000,
  int? startedAtMs,
  int? updatedAtMs,
}) {
  final now = DateTime.now().millisecondsSinceEpoch;
  String recipeFor(int flat) {
    if (flat < 7) return 'r1';
    if (flat < 11) return 'r2';
    return 'r3';
  }
  int localFor(int flat) {
    if (flat < 7) return flat;
    if (flat < 11) return flat - 7;
    return flat - 11;
  }
  final activeId = recipeFor(currentStep);
  final currentMap = <String, int>{'r1': 0, 'r2': 0, 'r3': 0};
  currentMap[activeId] = localFor(currentStep);
  final completedMap = <String, Set<int>>{
    'r1': <int>{},
    'r2': <int>{},
    'r3': <int>{},
  };
  for (final flat in completed) {
    if (flat < 0) continue;
    completedMap[recipeFor(flat)]!.add(localFor(flat));
  }
  return CookSessionState(
    targetKind: CookTargetKind.meal,
    targetId: mealId,
    startedAtMs: startedAtMs ?? (now - cumulativeElapsedMs),
    cumulativeElapsedMs: cumulativeElapsedMs,
    activeRecipeId: activeId,
    currentStepByRecipe: currentMap,
    completedStepsByRecipe: completedMap,
    checkedIngredients: checkedIngredients,
    activeTimers: timers,
    updatedAtMs: updatedAtMs ?? now,
  );
}

/// Prime SharedPreferences with a raw v1 JSON payload (pre-cmmrf-2
/// wire shape). Used by the migration-compat test to verify the
/// resume-gate copy survives the v1→v2 unpack.
Future<void> _primeV1Meal(
  String mealId, {
  required int currentStep,
  List<int> completed = const [],
}) async {
  final prefs = await SharedPreferences.getInstance();
  final now = DateTime.now().millisecondsSinceEpoch;
  final payload = {
    'schema_version': 1,
    'target_kind': 'meal',
    'target_id': mealId,
    'started_at_ms': now - 300000,
    'cumulative_elapsed_ms': 300000,
    'current_step': currentStep,
    'completed_steps': completed,
    'checked_ingredients': const [],
    'active_timers': const [],
    'updated_at_ms': now,
  };
  await prefs.setString(
    CookSessionKey.forMeal(mealId),
    jsonEncode(payload),
  );
}

Future<void> _prime(String mealId, CookSessionState state) async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setString(
    CookSessionKey.forMeal(mealId),
    jsonEncode(state.toJson()),
  );
}

void main() {
  setUpAll(() async {
    TestWidgetsFlutterBinding.ensureInitialized();
    if (!dotenv.isInitialized) {
      await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
    }
  });

  setUp(() => SharedPreferences.setMockInitialValues({}));
  tearDown(_tearDown);

  Meal _threeCompMeal() => Meal(
        id: 'meal-1',
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

  Map<String, Map<String, dynamic>> _threeCompRecipes() => {
        'r1': _recipe('r1', 'Dressing', 7, ingredientCount: 3),
        'r2': _recipe('r2', 'Salad', 4, ingredientCount: 2),
        'r3': _recipe('r3', 'Grilled Chicken', 9, ingredientCount: 1),
      };

  testWidgets('Resume gate with section-aware copy', (tester) async {
    await _setUp(meal: _threeCompMeal(), recipes: _threeCompRecipes());
    await _prime('meal-1', _seed(mealId: 'meal-1', currentStep: 9));
    // flat-step 9 in [7,4,9] plan → Salad · step 3 of 4.

    await _pump(tester, 'meal-1');

    expect(find.text('Resume'), findsOneWidget);
    expect(find.text('Start Over'), findsOneWidget);
    expect(find.textContaining('Salad · step 3 of 4'), findsOneWidget);
  });

  testWidgets(
      'cmmrf-2 — v1 meal payload resume-gate copy is preserved '
      'through the v1→v2 unpack',
      (tester) async {
    await _setUp(meal: _threeCompMeal(), recipes: _threeCompRecipes());
    // Write a raw v1 JSON payload directly (pre-cmmrf-2 wire shape).
    // Flat-step 9 in the [7,4,9] plan = Salad · step 3 of 4; after
    // fromJson migration + unpackLegacyMeal the gate copy should
    // match exactly.
    await _primeV1Meal(
      'meal-1',
      currentStep: 9,
      completed: const [0, 1, 2, 3, 4, 5, 6, 7, 8],
    );

    await _pump(tester, 'meal-1');

    expect(find.text('Resume'), findsOneWidget);
    expect(find.textContaining('Salad · step 3 of 4'), findsOneWidget);
  });

  testWidgets('Resume restores _currentStep + completed + ingredients',
      (tester) async {
    await _setUp(meal: _threeCompMeal(), recipes: _threeCompRecipes());
    // Salad · step 3 = flat 9; check Dressing's first 2 ingredients.
    await _prime(
      'meal-1',
      _seed(
        mealId: 'meal-1',
        currentStep: 9,
        completed: const [0, 1, 2, 3, 4, 5, 6, 7, 8],
        checkedIngredients: const ['0:0', '0:1'],
      ),
    );
    await _pump(tester, 'meal-1');

    await tester.tap(find.text('Resume'));
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }
    // Section header reflects restored step.
    expect(find.text('Salad'), findsAtLeast(1));
    expect(find.text('Step 3 of Salad'), findsOneWidget);
  });

  testWidgets('Start Over clears prefs key + mounts at flat-step 0',
      (tester) async {
    await _setUp(meal: _threeCompMeal(), recipes: _threeCompRecipes());
    await _prime('meal-1', _seed(mealId: 'meal-1', currentStep: 9));
    await _pump(tester, 'meal-1');

    await tester.tap(find.text('Start Over'));
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.containsKey(CookSessionKey.forMeal('meal-1')), isFalse);
    expect(find.text('Step 1 of Dressing'), findsOneWidget);
  });

  testWidgets('meal-version drift: clamps current_step + drift snackbar',
      (tester) async {
    await _setUp(meal: _threeCompMeal(), recipes: _threeCompRecipes());
    // currentStep = 99, but plan totalSteps = 20. Clamp to 19.
    await _prime('meal-1', _seed(mealId: 'meal-1', currentStep: 99));
    await _pump(tester, 'meal-1');

    await tester.tap(find.text('Resume'));
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }
    expect(
      find.textContaining('Meal changed since your last session'),
      findsOneWidget,
    );
  });

  testWidgets(
      'stable-key drift: orphan key dropped, ingredients-changed snackbar',
      (tester) async {
    await _setUp(meal: _threeCompMeal(), recipes: _threeCompRecipes());
    // 0:0 lives; 1:99 doesn't (Salad has 2 ingredients, indexes 0,1).
    await _prime(
      'meal-1',
      _seed(
        mealId: 'meal-1',
        currentStep: 0,
        completed: const [],
        checkedIngredients: const ['0:0', '1:99'],
      ),
    );
    await _pump(tester, 'meal-1');

    await tester.tap(find.text('Resume'));
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }
    expect(
      find.textContaining('Ingredients changed since your last session'),
      findsOneWidget,
    );
  });

  testWidgets('expired timer fires "while you were away" snackbar',
      (tester) async {
    await _setUp(meal: _threeCompMeal(), recipes: _threeCompRecipes());
    final past =
        DateTime.now().subtract(const Duration(minutes: 1)).millisecondsSinceEpoch;
    await _prime(
      'meal-1',
      _seed(
        mealId: 'meal-1',
        currentStep: 0,
        timers: [
          SavedTimerState(
            label: 'Dressing · simmer',
            deadlineMs: past,
            totalDurationSeconds: 300,
            source: 'manual',
          ),
        ],
      ),
    );
    await _pump(tester, 'meal-1');

    await tester.tap(find.text('Resume'));
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }
    expect(
      find.textContaining('Dressing · simmer timer finished'),
      findsOneWidget,
    );
  });
}
