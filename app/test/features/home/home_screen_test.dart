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
import 'package:palateful/features/recipes/add_recipe/batch_parser_service.dart';
import 'package:palateful/features/recipe_books/services/recipe_book_service.dart';

Response<dynamic> _fakeResponse(dynamic data) {
  return Response(
    data: data,
    requestOptions: RequestOptions(path: ''),
    statusCode: 200,
  );
}

/// Minimal fake that overrides only the methods called by HomeScreen.
class _FakeApiClient extends ApiClient {
  final Map<String, dynamic>? todayMealEvent;
  final List<Map<String, dynamic>> recipeBooks;

  _FakeApiClient({
    this.todayMealEvent,
    this.recipeBooks = const [],
  });

  @override
  Future<Response> getRecipeBooks({int limit = 20, int offset = 0}) async =>
      _fakeResponse({'items': recipeBooks});

  @override
  Future<Response> getFavorites() async => _fakeResponse({'items': []});

  @override
  Future<Response> listMeals({
    int? limit,
    int offset = 0,
    bool includeArchived = false,
    bool? archived,
    String? scope,
    String? q,
  }) async =>
      _fakeResponse({'items': <Map<String, dynamic>>[], 'total': 0});

  @override
  Future<Response> getRecipeBook(String id) async => _fakeResponse({
        'id': id,
        'name': 'Dinners',
        'recipes': <Map<String, dynamic>>[],
      });

  @override
  Future<Response> getMealEventsForToday() async {
    if (todayMealEvent != null) {
      return _fakeResponse({
        'items': [todayMealEvent],
        'total': 1,
      });
    }
    return _fakeResponse({'items': [], 'total': 0});
  }

  @override
  Future<Response> getRecentlyCookedRecipes({int limit = 5}) async =>
      _fakeResponse({'items': [], 'total': 0});
}

void _registerFakes(_FakeApiClient client) {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  gi.registerSingleton<ApiClient>(client);
  if (gi.isRegistered<BatchParserService>()) gi.unregister<BatchParserService>();
  gi.registerLazySingleton<BatchParserService>(() => BatchParserService());
  if (gi.isRegistered<RecipeBookService>()) {
    gi.unregister<RecipeBookService>();
  }
  gi.registerLazySingleton<RecipeBookService>(() => RecipeBookService(client));
  if (gi.isRegistered<AuthService>()) gi.unregister<AuthService>();
  gi.registerSingleton<AuthService>(AuthService());
  // Intentionally NOT registering SharedStateService — the provider
  // tolerates its absence; registering it here would pull in a
  // platform-channel-bound debounce timer that leaks across tests.
}

void _unregister() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  if (gi.isRegistered<BatchParserService>()) gi.unregister<BatchParserService>();
  if (gi.isRegistered<AuthService>()) gi.unregister<AuthService>();
}

void main() {
  setUpAll(() async {
    // Initialize dotenv with an empty map so ApiClient constructor can read env vars
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  setUp(() {
    // Swallow platform-channel writes so SharedStateService.syncRecipeBooks
    // (fires on first home-content load) doesn't throw under test.
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, (_) async => null);
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, null);
    _unregister();
  });

  group('HomeScreen — hero card', () {
    testWidgets('shows timing chip when meal event has prep and cook time',
        (tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      _registerFakes(_FakeApiClient(
        todayMealEvent: {
          'id': 'evt-1',
          'title': 'Test Dinner',
          'scheduled_at': DateTime.now().toIso8601String(),
          'meal_type': 'dinner',
          'status': 'planned',
          'is_shared': true,
          'owner_id': 'u1',
          'recipe': {
            'id': 'r1',
            'name': 'Pasta Carbonara',
            'image_url': null,
            'prep_time': 15,
            'cook_time': 20,
          },
        },
      ));

      await tester.pumpWidget(const ProviderScope(
        child: MaterialApp(home: HomeScreen()),
      ));
      // rf-3: homeContentProvider resolves across a couple of frames
      // (future settle → ref.listen → setState).
      for (var i = 0; i < 5; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }

      expect(find.text('35 min'), findsOneWidget);
    });

    testWidgets('hides timing chip when meal event has no timing info',
        (tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      _registerFakes(_FakeApiClient(
        todayMealEvent: {
          'id': 'evt-1',
          'title': 'Test Dinner',
          'scheduled_at': DateTime.now().toIso8601String(),
          'meal_type': 'dinner',
          'status': 'planned',
          'is_shared': true,
          'owner_id': 'u1',
          'recipe': {
            'id': 'r1',
            'name': 'Pasta Carbonara',
            'image_url': null,
            'prep_time': null,
            'cook_time': null,
          },
        },
      ));

      await tester.pumpWidget(const ProviderScope(
        child: MaterialApp(home: HomeScreen()),
      ));
      await tester.pump();

      expect(find.textContaining(RegExp(r'^\d+ min$')), findsNothing);
    });
  });

  group('HomeScreen — header + books nav', () {
    testWidgets('Recipe Books icon is rendered in the header',
        (tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      _registerFakes(_FakeApiClient());

      await tester.pumpWidget(const ProviderScope(
        child: MaterialApp(home: HomeScreen()),
      ));
      await tester.pump();

      // Identified via tooltip (more stable than tree position).
      expect(
        find.byTooltip('Recipe Books'),
        findsOneWidget,
      );
      // AI Assistant chat button was removed from the home header;
      // it now lives in Profile gated on is_admin (bugs-home-1).
      expect(find.byTooltip('AI Assistant'), findsNothing);
      // Batch photo import icon was removed from the header (home-polish-1);
      // photo import now lives solely behind the + FAB → Add Recipe sheet.
      expect(find.byTooltip('Import Photos'), findsNothing);
      expect(
        find.byWidgetPredicate((w) =>
            w is Icon && w.icon == Icons.add_photo_alternate_outlined),
        findsNothing,
      );
      // Remaining header destinations still present.
      expect(find.byTooltip('Pantry'), findsOneWidget);
    });

    testWidgets('My Books section is removed from home screen',
        (tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      _registerFakes(_FakeApiClient(
        recipeBooks: [
          {
            'id': 'book-1',
            'name': 'My Favorites',
            'recipe_count': 5,
          },
        ],
      ));

      await tester.pumpWidget(const ProviderScope(
        child: MaterialApp(home: HomeScreen()),
      ));
      for (var i = 0; i < 3; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }

      // The books section is gone entirely — header icon is the entry point.
      expect(find.text('My Books'), findsNothing);
      expect(find.text('See All'), findsNothing);
    });
  });
}
