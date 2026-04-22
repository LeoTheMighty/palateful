// hmp-3 — Home bulk actions: Create Meal, Add to Meal, Archive.
//
// Covers the wiring of the three bulk-bar dispatches on `home_screen.dart`
// against a fake ApiClient. Meal-service calls run through the registered
// `MealService(FakeApiClient)` so the stubs apply uniformly.

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/core/services/shared_state_service.dart';
import 'package:palateful/features/home/home_screen.dart';
import 'package:palateful/features/home/widgets/home_bulk_action_bar.dart';
import 'package:palateful/features/meals/services/meal_service.dart';
import 'package:palateful/features/meals/widgets/create_meal_sheet.dart';
import 'package:palateful/features/meals/widgets/meal_tile.dart';
import 'package:palateful/features/home/widgets/recipe_card.dart';
import 'package:palateful/features/recipes/add_recipe/batch_parser_service.dart';
import 'package:palateful/features/recipes/services/recipe_service.dart';

Response<dynamic> _fakeResponse(dynamic data, {int status = 200}) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: status,
    );

DioException _dio(int status) => DioException(
      requestOptions: RequestOptions(path: ''),
      response: Response(
        statusCode: status,
        requestOptions: RequestOptions(path: ''),
      ),
      type: DioExceptionType.badResponse,
    );

class _FakeApi extends ApiClient {
  final List<Map<String, dynamic>> recipes;
  final List<Map<String, dynamic>> meals;

  final List<List<String>> bulkArchiveCalls = [];
  final List<String> archiveMealCalls = [];
  final List<Map<String, String>> addRecipeCalls = [];

  Object? bulkArchiveError;
  Object? archiveMealError;
  Object? addRecipeError;

  _FakeApi({this.recipes = const [], this.meals = const []});

  @override
  Future<Response> getRecipeBooks({int limit = 20, int offset = 0}) async =>
      _fakeResponse({
        'items': [
          {'id': 'book-1', 'name': 'Dinners'}
        ]
      });

  @override
  Future<Response> getRecipeBook(String id) async => _fakeResponse({
        'id': id,
        'name': 'Dinners',
        'recipes': recipes,
      });

  @override
  Future<Response> getFavorites() async => _fakeResponse({
        'items': <Map<String, dynamic>>[],
        'total': 0,
        'favorited_meals': <Map<String, dynamic>>[],
      });

  @override
  Future<Response> listMeals({
    int? limit,
    int offset = 0,
    bool includeArchived = false,
    bool? archived,
    String? scope,
    String? q,
  }) async =>
      _fakeResponse({'items': meals, 'total': meals.length});

  @override
  Future<Response> getMealEventsForToday() async =>
      _fakeResponse({'items': <Map<String, dynamic>>[], 'total': 0});

  @override
  Future<Response> getRecentlyCookedRecipes({int limit = 5}) async =>
      _fakeResponse({'items': <Map<String, dynamic>>[], 'total': 0});

  @override
  Future<Response> bulkArchiveRecipes(List<String> recipeIds) async {
    bulkArchiveCalls.add(List.of(recipeIds));
    if (bulkArchiveError != null) throw bulkArchiveError!;
    return _fakeResponse({'archived': recipeIds.length});
  }

  @override
  Future<Response> archiveMeal(String mealId) async {
    archiveMealCalls.add(mealId);
    if (archiveMealError != null) throw archiveMealError!;
    return _fakeResponse({'id': mealId, 'archived_at': '2026-04-20T00:00:00Z'});
  }

  @override
  Future<Response> addRecipeToMeal(
    String mealId,
    Map<String, dynamic> data,
  ) async {
    addRecipeCalls.add({
      'meal_id': mealId,
      'recipe_id': data['recipe_id'] as String,
    });
    if (addRecipeError != null) throw addRecipeError!;
    // Return a minimal Meal JSON; only the side effects matter.
    return _fakeResponse({
      'id': mealId,
      'name': 'Some Meal',
      'recipe_book_id': 'book-1',
      'created_at': '2026-04-18T10:00:00Z',
      'updated_at': '2026-04-20T00:00:00Z',
      'components': [],
    });
  }
}

void _registerFakes(_FakeApi client) {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  gi.registerSingleton<ApiClient>(client);
  if (gi.isRegistered<MealService>()) gi.unregister<MealService>();
  gi.registerLazySingleton<MealService>(() => MealService(client));
  if (gi.isRegistered<RecipeService>()) gi.unregister<RecipeService>();
  gi.registerLazySingleton<RecipeService>(() => RecipeService(client));
  if (gi.isRegistered<BatchParserService>()) {
    gi.unregister<BatchParserService>();
  }
  gi.registerLazySingleton<BatchParserService>(() => BatchParserService());
  if (gi.isRegistered<AuthService>()) gi.unregister<AuthService>();
  gi.registerSingleton<AuthService>(AuthService());
  if (gi.isRegistered<SharedStateService>()) {
    gi.unregister<SharedStateService>();
  }
  gi.registerSingleton<SharedStateService>(SharedStateService());
}

void _unregister() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  if (gi.isRegistered<MealService>()) gi.unregister<MealService>();
  if (gi.isRegistered<RecipeService>()) gi.unregister<RecipeService>();
  if (gi.isRegistered<BatchParserService>()) {
    gi.unregister<BatchParserService>();
  }
  if (gi.isRegistered<AuthService>()) gi.unregister<AuthService>();
  if (gi.isRegistered<SharedStateService>()) {
    gi.unregister<SharedStateService>();
  }
}

Map<String, dynamic> _recipe({
  required String id,
  required String name,
  String updatedAt = '2026-04-01T00:00:00Z',
}) =>
    {
      'id': id,
      'name': name,
      'recipe_book_id': 'book-1',
      'recipe_book_name': 'Dinners',
      'updated_at': updatedAt,
      'created_at': updatedAt,
      'tags': <String>[],
    };

Map<String, dynamic> _mealSummary({
  required String id,
  required String name,
  List<String> componentRecipeIds = const [],
  String updatedAt = '2026-04-18T00:00:00Z',
}) =>
    {
      'id': id,
      'name': name,
      'recipe_book_id': 'book-1',
      'component_count': componentRecipeIds.length,
      'component_image_urls': <String>[],
      'component_recipe_ids': componentRecipeIds,
      'updated_at': updatedAt,
      'archived_at': null,
    };

Future<void> _pumpHome(WidgetTester tester) async {
  tester.view.physicalSize = const Size(1080, 2400);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(() {
    tester.view.resetPhysicalSize();
    tester.view.resetDevicePixelRatio();
  });
  await tester.pumpWidget(const ProviderScope(
    child: MaterialApp(home: HomeScreen()),
  ));
  await tester.pumpAndSettle();
  await tester.pump(const Duration(milliseconds: 300));
}

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  setUp(() {
    // Stub haptics — the long-press handler fires HapticFeedback.selectionClick
    // which otherwise leaks platform-channel noise into the test log.
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, (_) async => null);
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, null);
    _unregister();
  });

  group('Create Meal dispatch', () {
    testWidgets('long-press 2 recipes → tap Create Meal opens the sheet',
        (tester) async {
      _registerFakes(_FakeApi(recipes: [
        _recipe(id: 'r1', name: 'Kale Salad'),
        _recipe(id: 'r2', name: 'Lemon Dressing'),
      ]));
      await _pumpHome(tester);

      await tester.longPress(find.byType(RecipeCard).first);
      await tester.pumpAndSettle();
      await tester.tap(find.byType(RecipeCard).last);
      await tester.pumpAndSettle();

      // Bulk-bar primary reads "Create Meal" (enabled).
      expect(find.text('Create Meal'), findsOneWidget);

      await tester.tap(find.text('Create Meal'));
      await tester.pumpAndSettle();

      // CreateMealSheet opens with both recipes pre-filled.
      expect(find.byType(CreateMealSheet), findsOneWidget);
      // Name prefill is wired into the TextField's controller.
      expect(
        find.widgetWithText(TextField, 'Kale Salad + Lemon Dressing'),
        findsOneWidget,
      );
      // Both recipes render as preview cards inside the sheet.
      expect(find.text('Kale Salad'), findsWidgets);
      expect(find.text('Lemon Dressing'), findsWidgets);
    });
  });

  group('Add to Meal dispatch', () {
    testWidgets(
        'selecting only already-in-Meal recipes → snackbar + no API call',
        (tester) async {
      final api = _FakeApi(
        recipes: [_recipe(id: 'r1', name: 'Kale Salad')],
        meals: [
          _mealSummary(
            id: 'm1',
            name: 'Kale Salad Meal',
            componentRecipeIds: ['r1'],
          ),
        ],
      );
      _registerFakes(api);
      await _pumpHome(tester);

      // Long-press the Meal, then tap the recipe that's already inside it.
      await tester.longPress(find.byType(MealTile).first);
      await tester.pumpAndSettle();
      await tester.tap(find.byType(RecipeCard).first);
      await tester.pumpAndSettle();

      expect(find.text('Add to "Kale Salad Meal"'), findsOneWidget);
      await tester.tap(find.text('Add to "Kale Salad Meal"'));
      await tester.pumpAndSettle();

      expect(
        find.text('All selected recipes are already in this Meal'),
        findsOneWidget,
      );
      expect(api.addRecipeCalls, isEmpty);
    });

    testWidgets('happy path — dispatches once and shows success snackbar',
        (tester) async {
      final api = _FakeApi(
        recipes: [
          _recipe(id: 'r1', name: 'Kale Salad'),
          _recipe(id: 'r2', name: 'Miso Broccoli'),
        ],
        meals: [
          _mealSummary(
            id: 'm1',
            name: 'Kale Salad Meal',
            componentRecipeIds: ['r1'],
          ),
        ],
      );
      _registerFakes(api);
      await _pumpHome(tester);

      await tester.longPress(find.byType(MealTile).first);
      await tester.pumpAndSettle();
      // Grid sorts by updated_at DESC → [MealTile(m1), RecipeCard(r1),
      // RecipeCard(r2)]. r1 is already a component, so tap r2 (the new
      // recipe) via its display name.
      await tester.tap(find.widgetWithText(RecipeCard, 'Miso Broccoli'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Add to "Kale Salad Meal"'));
      await tester.pumpAndSettle();

      expect(api.addRecipeCalls, [
        {'meal_id': 'm1', 'recipe_id': 'r2'},
      ]);
      // Success snackbar (note: exact count + name).
      expect(
        find.textContaining('Added 1 recipe to Kale Salad Meal'),
        findsOneWidget,
      );
    });

    testWidgets('all failure — surfaces snackbar with View action',
        (tester) async {
      final api = _FakeApi(
        recipes: [
          _recipe(id: 'r1', name: 'Miso Broccoli'),
        ],
        meals: [
          _mealSummary(id: 'm1', name: 'Kale Salad Meal'),
        ],
      );
      api.addRecipeError = _dio(403);
      _registerFakes(api);
      await _pumpHome(tester);

      await tester.longPress(find.byType(MealTile).first);
      await tester.pumpAndSettle();
      await tester.tap(find.byType(RecipeCard).first);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Add to "Kale Salad Meal"'));
      await tester.pumpAndSettle();

      expect(find.text('Could not add recipes — see details'), findsOneWidget);
      expect(find.text('View'), findsOneWidget);
    });
  });

  group('Archive dispatch', () {
    testWidgets('confirm dialog cancel → no API call', (tester) async {
      final api = _FakeApi(
        recipes: [_recipe(id: 'r1', name: 'Kale Salad')],
      );
      _registerFakes(api);
      await _pumpHome(tester);

      await tester.longPress(find.byType(RecipeCard).first);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Archive'));
      await tester.pumpAndSettle();

      expect(find.text('Archive selected?'), findsOneWidget);
      await tester.tap(find.widgetWithText(TextButton, 'Cancel'));
      await tester.pumpAndSettle();

      expect(api.bulkArchiveCalls, isEmpty);
      expect(api.archiveMealCalls, isEmpty);
      // Selection stays active (Archive button still present).
      expect(find.byType(HomeBulkActionBar), findsOneWidget);
    });

    testWidgets('mixed recipe + Meal confirm → parallel archive dispatch',
        (tester) async {
      final api = _FakeApi(
        recipes: [_recipe(id: 'r1', name: 'Kale Salad')],
        meals: [_mealSummary(id: 'm1', name: 'Kale Salad Meal')],
      );
      _registerFakes(api);
      await _pumpHome(tester);

      // Long-press a recipe to enter selection mode, then tap the meal
      // tile to also select it.
      await tester.longPress(find.byType(RecipeCard).first);
      await tester.pumpAndSettle();
      await tester.tap(find.byType(MealTile).first);
      await tester.pumpAndSettle();

      await tester.tap(find.text('Archive'));
      await tester.pumpAndSettle();

      expect(
        find.text(
          'Archive 1 recipe and 1 Meal? You can restore them later from Archive.',
        ),
        findsOneWidget,
      );
      await tester.tap(find.widgetWithText(ElevatedButton, 'Archive'));
      await tester.pumpAndSettle();

      expect(api.bulkArchiveCalls, [
        ['r1'],
      ]);
      expect(api.archiveMealCalls, ['m1']);
      expect(find.text('Archived 2 items'), findsOneWidget);
    });

    testWidgets('partial failure — View action opens dialog with failed row',
        (tester) async {
      final api = _FakeApi(
        recipes: [_recipe(id: 'r1', name: 'Kale Salad')],
        meals: [_mealSummary(id: 'm1', name: 'Kale Salad Meal')],
      );
      api.archiveMealError = _dio(409); // Meal archive fails, recipes succeed.
      _registerFakes(api);
      await _pumpHome(tester);

      await tester.longPress(find.byType(RecipeCard).first);
      await tester.pumpAndSettle();
      await tester.tap(find.byType(MealTile).first);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Archive'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(ElevatedButton, 'Archive'));
      await tester.pumpAndSettle();

      expect(find.text('Archived 1 of 2 — see details'), findsOneWidget);
      await tester.tap(find.text('View'));
      await tester.pumpAndSettle();
      expect(find.text('Some items could not be archived'), findsOneWidget);
      // Dialog row is keyed per target so it's unambiguous even when the
      // MealTile still renders its name in the grid underneath.
      expect(
        find.byKey(const ValueKey('bulk-failure-Kale Salad Meal')),
        findsOneWidget,
      );
      expect(find.text('Conflict — try again'), findsOneWidget);
    });
  });
}
