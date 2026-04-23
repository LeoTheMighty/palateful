import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/meals/meal_detail_screen.dart';
import 'package:palateful/features/meals/meal_edit_screen.dart';
import 'package:palateful/features/meals/models/meal.dart';
import 'package:palateful/features/meals/services/meal_service.dart';

class _FakeApi extends ApiClient {}

class _FakeMealService extends MealService {
  Meal stubbedMeal;
  int favoriteCalls = 0;
  int unfavoriteCalls = 0;
  int archiveCalls = 0;
  int shareCalls = 0;
  Object? favoriteError;
  Object? archiveError;
  Object? shareError;
  String stubbedToken = 'TOKENAAAAAAAAAAAAAAA'; // 20-char URL-safe token

  _FakeMealService.empty()
      : stubbedMeal = Meal(
          id: 'meal-1',
          name: 'Kale Salad Meal',
          description: 'a test',
          recipeBookId: 'book-1',
          createdAt: DateTime.parse('2026-04-18T10:00:00Z'),
          updatedAt: DateTime.parse('2026-04-18T10:00:00Z'),
          components: const [
            MealComponent(
              recipeId: 'r1',
              name: 'Kale Salad',
              orderIndex: 0,
              imageUrl: null,
            ),
            MealComponent(
              recipeId: 'r2',
              name: 'Lemon Dressing',
              orderIndex: 1,
            ),
          ],
        ),
        super(_FakeApi());

  @override
  Future<Meal> getMeal(String mealId) async => stubbedMeal;

  @override
  Future<bool> favoriteMeal(String mealId, {required String bookId}) async {
    favoriteCalls++;
    if (favoriteError != null) throw favoriteError!;
    return true;
  }

  @override
  Future<bool> unfavoriteMeal(String mealId, {required String bookId}) async {
    unfavoriteCalls++;
    if (favoriteError != null) throw favoriteError!;
    return false;
  }

  @override
  Future<void> archiveMeal(String mealId, {required String bookId}) async {
    archiveCalls++;
    if (archiveError != null) throw archiveError!;
  }

  @override
  Future<ShareMealResult> share(String mealId) async {
    shareCalls++;
    if (shareError != null) throw shareError!;
    return ShareMealResult(
      token: stubbedToken,
      deepLink: 'palateful://meal-public/$stubbedToken',
    );
  }
}

Widget _harness(_FakeMealService svc, String mealId) {
  final router = GoRouter(
    routes: [
      GoRoute(
        path: '/',
        builder: (_, __) => MealDetailScreen(mealId: mealId),
      ),
      GoRoute(
        path: '/meals/:id/edit',
        builder: (_, state) =>
            MealEditScreen(mealId: state.pathParameters['id']!),
      ),
      GoRoute(
        path: '/recipes/:id',
        builder: (_, state) => Scaffold(
          body: Center(child: Text('recipe ${state.pathParameters['id']}')),
        ),
      ),
    ],
  );
  return ProviderScope(
    child: MaterialApp.router(routerConfig: router),
  );
}

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  late _FakeMealService service;

  setUp(() {
    service = _FakeMealService.empty();
    final g = GetIt.instance;
    if (g.isRegistered<MealService>()) g.unregister<MealService>();
    g.registerSingleton<MealService>(service);
  });

  tearDown(() {
    final g = GetIt.instance;
    if (g.isRegistered<MealService>()) g.unregister<MealService>();
  });

  testWidgets('renders meal name, description, components', (tester) async {
    await tester.pumpWidget(_harness(service, 'meal-1'));
    await tester.pumpAndSettle();

    expect(find.text('Kale Salad Meal'), findsOneWidget);
    expect(find.text('a test'), findsOneWidget);
    expect(find.text('Kale Salad'), findsOneWidget);
    expect(find.text('Lemon Dressing'), findsOneWidget);
    expect(find.text('Recipes (2)'), findsOneWidget);
  });

  testWidgets('shows action bar with 6 actions', (tester) async {
    await tester.pumpWidget(_harness(service, 'meal-1'));
    await tester.pumpAndSettle();

    expect(find.text('Favorite'), findsOneWidget);
    expect(find.text('Plan'), findsOneWidget);
    expect(find.text('Shop'), findsOneWidget);
    expect(find.text('Share'), findsOneWidget);
    expect(find.text('Archive'), findsOneWidget);
    expect(find.text('Edit'), findsOneWidget);
  });

  testWidgets('favorite toggle calls favorite endpoint', (tester) async {
    await tester.pumpWidget(_harness(service, 'meal-1'));
    await tester.pumpAndSettle();

    // Initial state — outlined heart.
    expect(find.byIcon(Icons.favorite_border), findsOneWidget);

    await tester.tap(find.text('Favorite'));
    await tester.pumpAndSettle();

    expect(service.favoriteCalls, 1);
  });

  testWidgets('favorite error rolls back state and shows snackbar',
      (tester) async {
    service.favoriteError = DioException(
      requestOptions: RequestOptions(path: ''),
      type: DioExceptionType.badResponse,
    );
    await tester.pumpWidget(_harness(service, 'meal-1'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Favorite'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text("Couldn't favorite meal"), findsOneWidget);
    // State rolled back — icon stays at outline.
    expect(find.byIcon(Icons.favorite_border), findsOneWidget);
  });

  testWidgets('already-favorited meal shows filled heart + unfavorites',
      (tester) async {
    service.stubbedMeal = service.stubbedMeal.copyWith(isFavorite: true);
    await tester.pumpWidget(_harness(service, 'meal-1'));
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.favorite), findsOneWidget);

    await tester.tap(find.text('Favorite'));
    await tester.pumpAndSettle();
    expect(service.unfavoriteCalls, 1);
  });

  testWidgets('archive confirms then calls archive endpoint',
      (tester) async {
    await tester.pumpWidget(_harness(service, 'meal-1'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Archive'));
    await tester.pumpAndSettle();
    expect(find.text('Archive meal?'), findsOneWidget);

    await tester.tap(find.widgetWithText(ElevatedButton, 'Archive'));
    await tester.pumpAndSettle();

    expect(service.archiveCalls, 1);
  });

  testWidgets('archive cancel keeps the meal open', (tester) async {
    await tester.pumpWidget(_harness(service, 'meal-1'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Archive'));
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(TextButton, 'Cancel'));
    await tester.pumpAndSettle();

    expect(service.archiveCalls, 0);
    expect(find.text('Kale Salad Meal'), findsOneWidget);
  });

  testWidgets('partial-unavailability banner shows', (tester) async {
    service.stubbedMeal = service.stubbedMeal.copyWith(components: [
      const MealComponent(
        recipeId: 'r1',
        name: 'Kale',
        orderIndex: 0,
        available: false,
        lastKnownName: 'Kale (removed)',
      ),
      const MealComponent(recipeId: 'r2', name: 'Lemon', orderIndex: 1),
    ]);
    await tester.pumpWidget(_harness(service, 'meal-1'));
    await tester.pumpAndSettle();

    expect(
      find.text('Some components are unavailable.'),
      findsOneWidget,
    );
  });

  testWidgets('all-unavailable renders the blocking banner', (tester) async {
    service.stubbedMeal = service.stubbedMeal.copyWith(components: [
      const MealComponent(
        recipeId: 'r1',
        name: 'Kale',
        orderIndex: 0,
        available: false,
      ),
      const MealComponent(
        recipeId: 'r2',
        name: 'Lemon',
        orderIndex: 1,
        available: false,
      ),
    ]);
    await tester.pumpWidget(_harness(service, 'meal-1'));
    await tester.pumpAndSettle();

    expect(
      find.textContaining('All components are unavailable'),
      findsOneWidget,
    );
  });

  testWidgets('tapping Share calls MealService.share', (tester) async {
    await tester.pumpWidget(_harness(service, 'meal-1'));
    await tester.pumpAndSettle();

    // Share.share() throws MissingPluginException in the test harness;
    // we only assert the API call landed before the native share sheet.
    try {
      await tester.tap(find.text('Share'));
      await tester.pumpAndSettle();
    } catch (_) {
      // Expected from the share_plus platform channel under tests.
    }
    expect(service.shareCalls, 1);
  });

  testWidgets('share failure shows retry snackbar', (tester) async {
    service.shareError = DioException(
      requestOptions: RequestOptions(path: ''),
      type: DioExceptionType.badResponse,
    );
    await tester.pumpWidget(_harness(service, 'meal-1'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Share'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text("Couldn't share meal"), findsOneWidget);
  });

  testWidgets('plan/shop actions are live as of mcal-9; share is live',
      (tester) async {
    await tester.pumpWidget(_harness(service, 'meal-1'));
    await tester.pumpAndSettle();

    // Tooltips were removed once Plan-for-Date + Add-to-Shopping-List
    // became live (mcal-9).
    expect(find.byTooltip('Available when calendars ship'), findsNothing);
    expect(find.byTooltip('Schedule this meal first'), findsNothing);
    expect(find.byTooltip('Available when sharing ships'), findsNothing);

    // Both action labels render and each hosts an enabled InkWell (the
    // icon widget wraps label + glyph in one tap target).
    expect(find.text('Plan'), findsOneWidget);
    expect(find.text('Shop'), findsOneWidget);

    // Tapping Plan should not throw (it tries to open a modal; we don't
    // fully settle because the modal depends on MealCalendarService /
    // active-calendar wiring which aren't needed for the enablement
    // check).
    final planAncestor = find.ancestor(
      of: find.text('Plan'),
      matching: find.byType(InkWell),
    );
    expect(planAncestor, findsWidgets);
    final inkWell = tester.widget<InkWell>(planAncestor.first);
    expect(inkWell.onTap, isNotNull);

    final shopAncestor = find.ancestor(
      of: find.text('Shop'),
      matching: find.byType(InkWell),
    );
    final shopInk = tester.widget<InkWell>(shopAncestor.first);
    expect(shopInk.onTap, isNotNull);
  });

  // ------------------------------------------------------------------
  // cmm-2 AC4 / AC5 — "Start Cooking" FAB visibility rules.
  // ------------------------------------------------------------------

  group('cmm-2 Start Cooking FAB', () {
    testWidgets('visible + enabled for a 2-component meal (all available)',
        (tester) async {
      await tester.pumpWidget(_harness(service, 'meal-1'));
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('meal_start_cooking_fab')),
        findsOneWidget,
      );
      expect(find.text('Start Cooking'), findsOneWidget);
      expect(
        find.byKey(const Key('meal_start_cooking_fab_disabled')),
        findsNothing,
      );
    });

    testWidgets('hidden when meal has zero components', (tester) async {
      service.stubbedMeal =
          service.stubbedMeal.copyWith(components: const []);
      await tester.pumpWidget(_harness(service, 'meal-1'));
      await tester.pumpAndSettle();

      expect(find.text('Start Cooking'), findsNothing);
      expect(
        find.byKey(const Key('meal_start_cooking_fab')),
        findsNothing,
      );
      expect(
        find.byKey(const Key('meal_start_cooking_fab_disabled')),
        findsNothing,
      );
    });

    testWidgets('disabled with tooltip when all components unavailable',
        (tester) async {
      service.stubbedMeal = service.stubbedMeal.copyWith(components: const [
        MealComponent(
          recipeId: 'r1',
          name: 'Kale',
          orderIndex: 0,
          available: false,
        ),
        MealComponent(
          recipeId: 'r2',
          name: 'Lemon',
          orderIndex: 1,
          available: false,
        ),
      ]);
      await tester.pumpWidget(_harness(service, 'meal-1'));
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('meal_start_cooking_fab_disabled')),
        findsOneWidget,
      );
      expect(
        find.byTooltip('Add a recipe to start cooking'),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('meal_start_cooking_fab')),
        findsNothing,
      );
    });

    testWidgets('visible for single-component meal', (tester) async {
      service.stubbedMeal = service.stubbedMeal.copyWith(components: const [
        MealComponent(
          recipeId: 'r1',
          name: 'Solo',
          orderIndex: 0,
        ),
      ]);
      await tester.pumpWidget(_harness(service, 'meal-1'));
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('meal_start_cooking_fab')),
        findsOneWidget,
      );
    });
  });
}
