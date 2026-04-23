// cmm-2 — Widget tests for MealCookModeScreen: parallel meal+recipes
// load, partial-load banner, retry semantics, lifecycle paused-flush.
//
// cmm-3..cmm-7 layer in the section header, source-tagged ingredients,
// component-aware timers, multi-row post-cook sheet, and resume gate
// respectively; those acceptance criteria are covered in their own
// test files (`meal_cook_mode_sectioning_test.dart`, etc.).

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

/// ApiClient that serves meal cook GETs: per-recipe-id payload map +
/// optional Set of recipe ids that should error (partial-load).
class _FakeMealCookApi extends ApiClient {
  final Map<String, Map<String, dynamic>> recipePayloads;
  final Set<String> failingRecipeIds;

  _FakeMealCookApi({
    required this.recipePayloads,
    Set<String> failingRecipeIds = const {},
  }) : failingRecipeIds = Set<String>.from(failingRecipeIds);

  @override
  Future<Response> getRecipe(String recipeId, {bool debug = false, List<String>? include}) async {
    if (failingRecipeIds.contains(recipeId)) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/recipes/$recipeId'),
        type: DioExceptionType.badResponse,
        response: Response(
          requestOptions: RequestOptions(path: '/v1/recipes/$recipeId'),
          statusCode: 500,
        ),
      );
    }
    final payload = recipePayloads[recipeId];
    if (payload == null) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/recipes/$recipeId'),
        type: DioExceptionType.badResponse,
      );
    }
    return Response(
      data: payload,
      requestOptions: RequestOptions(path: '/v1/recipes/$recipeId'),
      statusCode: 200,
    );
  }

  @override
  Future<Response> getNotificationPreferences() async => Response(
        data: const {
          'categories': {'timers': true},
        },
        requestOptions: RequestOptions(path: ''),
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
  final Meal stubbedMeal;
  _FakeMealService(this.stubbedMeal, ApiClient api) : super(api);

  @override
  Future<Meal> getMeal(String mealId) async => stubbedMeal;
}

Map<String, dynamic> _recipePayload({
  required String id,
  required String name,
  int stepCount = 3,
  int ingredientCount = 2,
}) {
  return {
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
        'ingredient': {'canonical_name': 'Ing $i of $name'},
        'quantity_display': '1',
        'unit_display': 'cup',
      },
    ),
  };
}

Meal _buildMeal({
  required String id,
  required String name,
  required List<MealComponent> components,
}) =>
    Meal(
      id: id,
      name: name,
      recipeBookId: 'book-1',
      createdAt: DateTime(2026, 4, 22),
      updatedAt: DateTime(2026, 4, 22),
      components: components,
    );

Future<void> _setUpHarness({
  required Meal meal,
  required Map<String, Map<String, dynamic>> recipes,
  Set<String> failingRecipeIds = const {},
}) async {
  TestWidgetsFlutterBinding.ensureInitialized();
  if (!dotenv.isInitialized) {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  }
  final gi = GetIt.instance;
  final api = _FakeMealCookApi(
    recipePayloads: recipes,
    failingRecipeIds: failingRecipeIds,
  );
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

void _tearDownHarness() {
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
  final router = GoRouter(
    routes: [
      GoRoute(
        path: '/',
        builder: (_, __) => MealCookModeScreen(mealId: mealId),
      ),
    ],
  );
  return ProviderScope(
    child: MaterialApp.router(
      theme: AppTheme.light(),
      routerConfig: router,
    ),
  );
}

Future<void> _pumpAndLoad(WidgetTester tester, String mealId) async {
  tester.view.physicalSize = const Size(1080, 2400);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(() {
    tester.view.resetPhysicalSize();
    tester.view.resetDevicePixelRatio();
  });
  await tester.pumpWidget(_harness(mealId));
  // The cook-mode screen mounts a 1-second Timer.periodic, so
  // pumpAndSettle never settles. Drain the async load chain with
  // discrete pumps instead — the same pattern cook_mode_resume_test
  // uses for CookModeScreen. Wider window because each component
  // hits cacheRecipe() (an async SharedPreferences write).
  for (var i = 0; i < 20; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  setUpAll(() async {
    TestWidgetsFlutterBinding.ensureInitialized();
    if (!dotenv.isInitialized) {
      await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
    }
  });

  setUp(() {
    // RecipeCacheService.cacheRecipe writes to SharedPreferences on
    // every successful fetch — test needs a fresh mock per test so
    // cache writes don't leak between scenarios.
    SharedPreferences.setMockInitialValues({});
  });

  tearDown(_tearDownHarness);

  group('cmm-2 mount + load', () {
    testWidgets('mounts cook UI for a 3-component meal (all recipes succeed)',
        (tester) async {
      final meal = _buildMeal(
        id: 'meal-1',
        name: 'Salad Night',
        components: const [
          MealComponent(recipeId: 'r1', name: 'Dressing', orderIndex: 0),
          MealComponent(recipeId: 'r2', name: 'Salad', orderIndex: 1),
          MealComponent(
              recipeId: 'r3', name: 'Grilled Chicken', orderIndex: 2),
        ],
      );
      await _setUpHarness(
        meal: meal,
        recipes: {
          'r1': _recipePayload(id: 'r1', name: 'Dressing', stepCount: 7),
          'r2': _recipePayload(id: 'r2', name: 'Salad', stepCount: 4),
          'r3':
              _recipePayload(id: 'r3', name: 'Grilled Chicken', stepCount: 9),
        },
      );
      await _pumpAndLoad(tester, 'meal-1');

      // Header shows the meal name.
      expect(find.text('Salad Night'), findsWidgets);
      // No partial-load banner — every recipe loaded.
      expect(
        find.byKey(const Key('meal_cook_partial_load_banner')),
        findsNothing,
      );
      // Step card shows the first instruction.
      expect(find.text('Step 1 of Dressing'), findsOneWidget);
      // Manual timer header icon present.
      expect(find.byTooltip('Add a timer'), findsOneWidget);
    });

    testWidgets('all-component failure: cook UI mounts with all placeholders',
        (tester) async {
      // Edge case where every recipe fetch fails. The screen still
      // mounts (no error scaffold) so the user can hit Retry on any
      // component — partial-load degrade is the universal failure path.
      final meal = _buildMeal(
        id: 'meal-all-fail',
        name: 'All Failed',
        components: const [
          MealComponent(recipeId: 'r1', name: 'Dressing', orderIndex: 0),
          MealComponent(recipeId: 'r2', name: 'Salad', orderIndex: 1),
        ],
      );
      await _setUpHarness(
        meal: meal,
        recipes: const {},
        failingRecipeIds: const {'r1', 'r2'},
      );
      await _pumpAndLoad(tester, 'meal-all-fail');

      // Banner present.
      expect(
        find.byKey(const Key('meal_cook_partial_load_banner')),
        findsOneWidget,
      );
      // Placeholder shown for the first (failed) component immediately.
      expect(
        find.byKey(const Key('component_load_retry')),
        findsOneWidget,
      );
    });
  });

  group('cmm-2 partial-load degrade', () {
    testWidgets('partial failure: banner + cook UI mounts + placeholder',
        (tester) async {
      final meal = _buildMeal(
        id: 'meal-partial',
        name: 'Partial Meal',
        components: const [
          MealComponent(recipeId: 'r1', name: 'Dressing', orderIndex: 0),
          MealComponent(recipeId: 'r2', name: 'Salad', orderIndex: 1),
          MealComponent(
              recipeId: 'r3', name: 'Grilled Chicken', orderIndex: 2),
        ],
      );
      await _setUpHarness(
        meal: meal,
        recipes: {
          'r1': _recipePayload(id: 'r1', name: 'Dressing', stepCount: 7),
          'r2': _recipePayload(id: 'r2', name: 'Salad', stepCount: 4),
        },
        failingRecipeIds: const {'r3'},
      );
      await _pumpAndLoad(tester, 'meal-partial');

      // Partial-load banner present with the failing component name.
      expect(
        find.byKey(const Key('meal_cook_partial_load_banner')),
        findsOneWidget,
      );
      expect(
        find.textContaining('Grilled Chicken'),
        findsAtLeast(1),
      );

      // Cook UI still mounted on the first (Dressing) step.
      expect(find.text('Step 1 of Dressing'), findsOneWidget);
      expect(find.byKey(const Key('component_load_retry')), findsNothing);
    });

    testWidgets('placeholder + Retry visible when navigated into failed range',
        (tester) async {
      final meal = _buildMeal(
        id: 'meal-partial-2',
        name: 'Partial Meal 2',
        components: const [
          MealComponent(recipeId: 'r1', name: 'Dressing', orderIndex: 0),
          MealComponent(
              recipeId: 'r2', name: 'Grilled Chicken', orderIndex: 1),
        ],
      );
      await _setUpHarness(
        meal: meal,
        recipes: {
          'r1': _recipePayload(id: 'r1', name: 'Dressing', stepCount: 2),
        },
        failingRecipeIds: const {'r2'},
      );
      await _pumpAndLoad(tester, 'meal-partial-2');

      // 2 Dressing steps + 1 placeholder slot for Grilled Chicken =
      // totalSteps 3. Tap Next twice to land on the placeholder slot.
      await tester.tap(find.text('Next'));
      await tester.pump();
      await tester.tap(find.text('Next'));
      await tester.pump();

      // We should now be on Grilled Chicken's range (loadFailed).
      expect(
        find.byKey(const Key('component_load_retry')),
        findsOneWidget,
      );
      expect(
        find.textContaining("Grilled Chicken couldn't load"),
        findsAtLeast(1),
      );
    });

    testWidgets(
        'successful retry remaps _currentStep so the user does not teleport',
        (tester) async {
      // Plan starts as [Dressing(2 steps), GrilledChicken(placeholder=1)]
      // → totalSteps = 3. User advances to flat-step 2 (the placeholder
      // for Grilled Chicken). Retry succeeds with 5 real steps; new
      // totalSteps = 7. _currentStep must remap to flat-step 2 in the
      // new plan (still the FIRST step of Grilled Chicken, not some
      // random Dressing step).
      final meal = _buildMeal(
        id: 'meal-remap',
        name: 'Remap Meal',
        components: const [
          MealComponent(recipeId: 'r1', name: 'Dressing', orderIndex: 0),
          MealComponent(
              recipeId: 'r2', name: 'Grilled Chicken', orderIndex: 1),
        ],
      );
      final api = _FakeMealCookApi(
        recipePayloads: {
          'r1': _recipePayload(id: 'r1', name: 'Dressing', stepCount: 2),
          'r2': _recipePayload(
              id: 'r2', name: 'Grilled Chicken', stepCount: 5),
        },
        failingRecipeIds: const {'r2'},
      );
      TestWidgetsFlutterBinding.ensureInitialized();
      if (!dotenv.isInitialized) {
        await dotenv.load(
            mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
      }
      final gi = GetIt.instance;
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

      await _pumpAndLoad(tester, 'meal-remap');

      // Advance into Grilled Chicken's placeholder (flat-step 2).
      await tester.tap(find.text('Next'));
      await tester.pump();
      await tester.tap(find.text('Next'));
      await tester.pump();
      expect(
        find.byKey(const Key('component_load_retry')),
        findsOneWidget,
      );

      // Recover the failing recipe and tap the placeholder Retry.
      api.failingRecipeIds.remove('r2');
      await tester.tap(find.byKey(const Key('component_load_retry')));
      for (var i = 0; i < 6; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }

      // After remap the user is on flat-step 2 of the rebuilt plan,
      // which is "Step 1 of Grilled Chicken" — not teleported into
      // a Dressing step or stuck on the placeholder.
      expect(
        find.text('Step 1 of Grilled Chicken'),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('component_load_retry')),
        findsNothing,
      );
      expect(
        find.byKey(const Key('meal_cook_partial_load_banner')),
        findsNothing,
      );
    });

    testWidgets('offline cache fallback: surfaces Offline indicator',
        (tester) async {
      // Pre-cache a recipe payload, then make the live fetch raise a
      // connection error. The component should still load (from cache)
      // and the header should render the "Offline" badge.
      final meal = _buildMeal(
        id: 'meal-offline',
        name: 'Offline Meal',
        components: const [
          MealComponent(recipeId: 'r1', name: 'Dressing', orderIndex: 0),
        ],
      );
      TestWidgetsFlutterBinding.ensureInitialized();
      if (!dotenv.isInitialized) {
        await dotenv.load(
            mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
      }
      // Wire the cache with a pre-cached payload.
      final cacheService = RecipeCacheService();
      await cacheService.cacheRecipe(
        'r1',
        _recipePayload(id: 'r1', name: 'Dressing', stepCount: 2),
      );

      // Use an api that throws a connection error for /v1/recipes/r1.
      final api = _OfflineFakeApi();

      final gi = GetIt.instance;
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
      gi.registerSingleton<RecipeCacheService>(cacheService);

      await _pumpAndLoad(tester, 'meal-offline');

      expect(find.byIcon(Icons.wifi_off), findsOneWidget);
      expect(find.text('Offline'), findsOneWidget);
      expect(find.text('Step 1 of Dressing'), findsOneWidget);
    });

    testWidgets('Retry on banner re-fetches the failing recipe', (tester) async {
      final meal = _buildMeal(
        id: 'meal-retry',
        name: 'Retry Meal',
        components: const [
          MealComponent(recipeId: 'r1', name: 'Dressing', orderIndex: 0),
          MealComponent(recipeId: 'r2', name: 'Salad', orderIndex: 1),
        ],
      );
      // Use a mutable failing set so retry can succeed on the second try.
      final api = _FakeMealCookApi(
        recipePayloads: {
          'r1': _recipePayload(id: 'r1', name: 'Dressing', stepCount: 2),
          'r2': _recipePayload(id: 'r2', name: 'Salad', stepCount: 2),
        },
        failingRecipeIds: const {'r2'},
      );
      TestWidgetsFlutterBinding.ensureInitialized();
      if (!dotenv.isInitialized) {
        await dotenv.load(
            mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
      }
      final gi = GetIt.instance;
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

      await _pumpAndLoad(tester, 'meal-retry');

      // Banner present.
      expect(
        find.byKey(const Key('meal_cook_partial_load_banner')),
        findsOneWidget,
      );

      // Make r2 succeed on the next call. The new ApiClient should be
      // queried by `_retryComponent` via getIt — but our existing
      // singleton is the same instance, so update its failing set.
      api.failingRecipeIds.remove('r2');

      // Tap the banner Retry.
      await tester.tap(find.text('Retry'));
      for (var i = 0; i < 5; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }

      // After retry the banner should be gone and the plan rebuilt.
      expect(
        find.byKey(const Key('meal_cook_partial_load_banner')),
        findsNothing,
      );
    });
  });
}

/// ApiClient that always raises a connection-class DioException for
/// `getRecipe`. Used to drive the offline-cache fallback path.
class _OfflineFakeApi extends ApiClient {
  @override
  Future<Response> getRecipe(String recipeId, {bool debug = false, List<String>? include}) async {
    throw DioException(
      requestOptions: RequestOptions(path: '/v1/recipes/$recipeId'),
      type: DioExceptionType.connectionError,
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

