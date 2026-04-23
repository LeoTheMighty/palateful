// rf-6 — End-to-end reactive foundation regression.
//
// Scripted dogfood session as a widget test: the ground-truth proof the
// epic's single-measurable-proof asks for, at CI cadence.
//
// Flow:
//   1. Pump HomeScreen with one initial recipe.
//   2. Invoke `RecipeService.createRecipe` through the registered DI.
//   3. The service emits `RecipeCreated` on the bus.
//   4. `homeContentProvider` invalidates on the event, refetches, and
//      the new recipe tile renders WITHOUT a pull-to-refresh gesture.
//
// This exercises ALL three rf-layers end-to-end:
//   rf-1 — MutationBus primitive delivers the event.
//   rf-3 — homeContentProvider's bus subscription fires invalidateSelf.
//   rf-4 — RecipeService emits RecipeCreated on success.

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/features/home/home_screen.dart';
import 'package:palateful/features/home/widgets/recipe_card.dart';
import 'package:palateful/features/meals/services/meal_service.dart';
import 'package:palateful/features/recipes/add_recipe/batch_parser_service.dart';
import 'package:palateful/features/recipe_books/services/recipe_book_service.dart';
import 'package:palateful/features/recipes/services/recipe_service.dart';
import 'package:palateful/shared/widgets/shimmer_loading.dart';

Response<dynamic> _ok(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _EndToEndApi extends ApiClient {
  List<Map<String, dynamic>> recipes;
  int getRecipeBookCalls = 0;

  _EndToEndApi({required this.recipes});

  @override
  Future<Response> getRecipeBooks({int limit = 20, int offset = 0}) async =>
      _ok({
        'items': [
          {'id': 'book-1', 'name': 'Dinners'}
        ],
      });

  @override
  Future<Response> getRecipeBook(String id) async {
    getRecipeBookCalls++;
    return _ok({'id': id, 'name': 'Dinners', 'recipes': recipes});
  }

  @override
  Future<Response> getFavorites() async => _ok({
        'items': <Map<String, dynamic>>[],
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
      _ok({'items': <Map<String, dynamic>>[], 'total': 0});

  @override
  Future<Response> getMealEventsForToday() async =>
      _ok({'items': <Map<String, dynamic>>[], 'total': 0});

  @override
  Future<Response> getRecentlyCookedRecipes({int limit = 5}) async =>
      _ok({'items': <Map<String, dynamic>>[], 'total': 0});

  @override
  Future<Response> createRecipe(String bookId, Map<String, dynamic> data) async {
    // Mirror the backend: append the new recipe to the book's list so the
    // next getRecipeBook response picks it up.
    final created = {
      'id': 'r-new',
      'name': data['name'] ?? 'Untitled',
      'recipe_book_id': bookId,
      'meal_type': 'dinner',
      'updated_at': '2026-04-22T10:00:00Z',
      'created_at': '2026-04-22T10:00:00Z',
      'tags': <String>[],
    };
    recipes = [...recipes, created];
    return _ok(created);
  }
}

Map<String, dynamic> _recipe({required String id, required String name}) => {
      'id': id,
      'name': name,
      'recipe_book_id': 'book-1',
      'recipe_book_name': 'Dinners',
      'meal_type': 'dinner',
      'updated_at': '2026-04-01T00:00:00Z',
      'created_at': '2026-04-01T00:00:00Z',
      'tags': <String>[],
    };

void _register(_EndToEndApi client) {
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
  if (gi.isRegistered<RecipeBookService>()) {
    gi.unregister<RecipeBookService>();
  }
  gi.registerLazySingleton<RecipeBookService>(() => RecipeBookService(client));
  if (gi.isRegistered<AuthService>()) gi.unregister<AuthService>();
  gi.registerSingleton<AuthService>(AuthService());
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
}

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  setUp(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, (_) async => null);
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, null);
    _unregister();
  });

  testWidgets(
    'end-to-end: save a recipe → Home tile visible with no pull-to-refresh',
    (tester) async {
      final api = _EndToEndApi(recipes: [
        _recipe(id: 'r-existing', name: 'Existing Dinner'),
      ]);
      _register(api);

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

      expect(find.text('Existing Dinner'), findsOneWidget);
      expect(find.byType(RecipeCard), findsOneWidget);
      expect(api.getRecipeBookCalls, 1);

      // Drive the full end-to-end path: call RecipeService.createRecipe
      // the way the recipe wizard would. Service emits on success; the
      // home provider's bus subscription invalidates and refetches.
      await GetIt.instance<RecipeService>().createRecipe('book-1', {
        'name': 'Fresh Pasta',
      });

      // Drain the refetch.
      await tester.pumpAndSettle();

      expect(find.text('Fresh Pasta'), findsOneWidget,
          reason: 'new recipe tile must appear WITHOUT a pull-to-refresh');
      expect(find.text('Existing Dinner'), findsOneWidget,
          reason: 'existing tile must stay in place');
      expect(find.byType(RecipeCard), findsNWidgets(2));
      expect(find.byType(ShimmerCard), findsNothing,
          reason: 'no skeleton flash between invalidation and AsyncData');
      expect(api.getRecipeBookCalls, 2,
          reason: 'exactly one refetch from the bus event');
    },
  );
}
