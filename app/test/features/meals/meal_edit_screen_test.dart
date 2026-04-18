import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/meals/meal_edit_screen.dart';
import 'package:palateful/features/meals/models/meal.dart';
import 'package:palateful/features/meals/services/meal_service.dart';

class _FakeApi extends ApiClient {}

class _FakeMealService extends MealService {
  Meal stubbedMeal;
  List<String>? lastReorderIds;
  String? lastRemovedRecipeId;
  Map<String, dynamic>? lastUpdatePayload;

  bool reorderThrows = false;

  _FakeMealService.withComponents(List<MealComponent> components)
      : stubbedMeal = Meal(
          id: 'meal-1',
          name: 'Original Name',
          description: 'Original desc',
          recipeBookId: 'book-1',
          createdAt: DateTime.parse('2026-04-18T10:00:00Z'),
          updatedAt: DateTime.parse('2026-04-18T10:00:00Z'),
          components: components,
        ),
        super(_FakeApi());

  @override
  Future<Meal> getMeal(String mealId) async => stubbedMeal;

  @override
  Future<Meal> updateMeal(
    String mealId, {
    String? name,
    String? description,
  }) async {
    lastUpdatePayload = {'name': name, 'description': description};
    return stubbedMeal;
  }

  @override
  Future<Meal> reorderMealComponents(
    String mealId,
    List<String> recipeIds,
  ) async {
    if (reorderThrows) {
      throw MealReorderMismatchException();
    }
    lastReorderIds = recipeIds;
    return stubbedMeal;
  }

  @override
  Future<Meal> removeRecipeFromMeal(
    String mealId,
    String recipeId,
  ) async {
    lastRemovedRecipeId = recipeId;
    return stubbedMeal;
  }
}

MealComponent _c(String id, String name, int idx) =>
    MealComponent(recipeId: id, name: name, orderIndex: idx);

Widget _harness(_FakeMealService svc, {String id = 'meal-1'}) {
  final router = GoRouter(
    routes: [
      GoRoute(path: '/', builder: (_, __) => MealEditScreen(mealId: id)),
    ],
  );
  return ProviderScope(child: MaterialApp.router(routerConfig: router));
}

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  late _FakeMealService service;

  setUp(() {
    service = _FakeMealService.withComponents([
      _c('r1', 'Kale Salad', 0),
      _c('r2', 'Lemon Dressing', 1),
      _c('r3', 'Garlic Bread', 2),
    ]);
    final g = GetIt.instance;
    if (g.isRegistered<MealService>()) g.unregister<MealService>();
    g.registerSingleton<MealService>(service);
    if (g.isRegistered<ApiClient>()) g.unregister<ApiClient>();
    g.registerSingleton<ApiClient>(_FakeApi());
  });

  tearDown(() {
    final g = GetIt.instance;
    if (g.isRegistered<MealService>()) g.unregister<MealService>();
    if (g.isRegistered<ApiClient>()) g.unregister<ApiClient>();
  });

  testWidgets('renders with pre-filled name + description', (tester) async {
    await tester.pumpWidget(_harness(service));
    await tester.pumpAndSettle();

    expect(find.text('Edit meal'), findsOneWidget);
    final nameField = tester.widget<TextField>(
      find.widgetWithText(TextField, 'Name'),
    );
    expect(nameField.controller?.text, 'Original Name');
    final descField = tester.widget<TextField>(
      find.widgetWithText(TextField, 'Description'),
    );
    expect(descField.controller?.text, 'Original desc');
    expect(find.text('Recipes (3)'), findsOneWidget);
  });

  testWidgets('tapping Save calls updateMeal with new name + description',
      (tester) async {
    await tester.pumpWidget(_harness(service));
    await tester.pumpAndSettle();

    await tester.enterText(
      find.widgetWithText(TextField, 'Name'),
      'New Name',
    );
    await tester.enterText(
      find.widgetWithText(TextField, 'Description'),
      'New desc',
    );
    await tester.tap(find.widgetWithText(TextButton, 'Save'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(service.lastUpdatePayload?['name'], 'New Name');
    expect(service.lastUpdatePayload?['description'], 'New desc');
  });

  testWidgets('swipe-to-delete at 3→2 succeeds and commits',
      (tester) async {
    await tester.pumpWidget(_harness(service));
    await tester.pumpAndSettle();

    // Swipe Garlic Bread off the list (endToStart).
    await tester.drag(find.text('Garlic Bread'), const Offset(-600, 0));
    await tester.pumpAndSettle();

    expect(service.lastRemovedRecipeId, 'r3');
    expect(find.text('Garlic Bread'), findsNothing);
  });

  testWidgets('swipe-to-delete at 2 rejects with snackbar', (tester) async {
    service = _FakeMealService.withComponents([
      _c('r1', 'Kale Salad', 0),
      _c('r2', 'Lemon Dressing', 1),
    ]);
    final g = GetIt.instance;
    if (g.isRegistered<MealService>()) g.unregister<MealService>();
    g.registerSingleton<MealService>(service);

    await tester.pumpWidget(_harness(service));
    await tester.pumpAndSettle();

    await tester.drag(find.text('Kale Salad'), const Offset(-600, 0));
    await tester.pumpAndSettle();

    expect(service.lastRemovedRecipeId, isNull);
    expect(
      find.textContaining('A meal needs at least 2 recipes'),
      findsOneWidget,
    );
    expect(find.text('Kale Salad'), findsOneWidget);
  });
}
