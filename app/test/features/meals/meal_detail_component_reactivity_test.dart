// rmc-1 AC #9 — MealComponentAdded event patches Meal detail in place.
//
// Pumps MealDetailScreen with a 2-component Meal, emits
// `MealComponentAdded(3-component-Meal)`, asserts the chip strip shows
// the new component without a refetch round-trip. `getMealCalls` is
// the no-refetch assertion: it must stay at 1 after the event.

import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/state/mutation_bus.dart';
import 'package:palateful/features/meals/meal_detail_screen.dart';
import 'package:palateful/features/meals/models/meal.dart';
import 'package:palateful/features/meals/services/meal_service.dart';

import '../../helpers/mutation_bus_test_helper.dart';

class _FakeApi extends ApiClient {}

class _FakeMealService extends MealService {
  _FakeMealService(this.initial) : super(_FakeApi());

  Meal initial;
  int getMealCalls = 0;

  @override
  Future<Meal> getMeal(String mealId) async {
    getMealCalls++;
    return initial;
  }
}

Meal _meal({
  String id = 'meal-1',
  required List<MealComponent> components,
}) =>
    Meal(
      id: id,
      name: 'Weeknight Pasta',
      recipeBookId: 'book-1',
      createdAt: DateTime.parse('2026-04-18T10:00:00Z'),
      updatedAt: DateTime.parse('2026-04-18T10:00:00Z'),
      components: components,
    );

MealComponent _comp(String id, String name, int idx) =>
    MealComponent(recipeId: id, name: name, orderIndex: idx);

Widget _harness(String mealId) {
  final router = GoRouter(
    routes: [
      GoRoute(
        path: '/',
        builder: (_, _) => MealDetailScreen(mealId: mealId),
      ),
      GoRoute(
        path: '/recipes/:id',
        builder: (_, state) => Scaffold(
          body: Center(child: Text('recipe ${state.pathParameters['id']}')),
        ),
      ),
    ],
  );
  return ProviderScope(child: MaterialApp.router(routerConfig: router));
}

Map<String, dynamic> _mealPayload({
  String id = 'meal-1',
  required List<Map<String, dynamic>> components,
}) =>
    {
      'id': id,
      'name': 'Weeknight Pasta',
      'recipe_book_id': 'book-1',
      'created_at': '2026-04-18T10:00:00Z',
      'updated_at': '2026-04-18T10:00:00Z',
      'is_favorite': false,
      'components': components,
    };

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  late _FakeMealService service;

  setUp(() {
    service = _FakeMealService(_meal(components: [
      _comp('r1', 'Spaghetti', 0),
      _comp('r2', 'Tomato Sauce', 1),
    ]));
    final g = GetIt.instance;
    if (g.isRegistered<MealService>()) g.unregister<MealService>();
    g.registerSingleton<MealService>(service);
  });

  tearDown(() {
    final g = GetIt.instance;
    if (g.isRegistered<MealService>()) g.unregister<MealService>();
  });

  testWidgets(
    'MealComponentAdded patches detail in place — no refetch',
    (tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });
      await tester.pumpWidget(_harness('meal-1'));
      await tester.pumpAndSettle();

      expect(find.text('Spaghetti'), findsOneWidget);
      expect(find.text('Tomato Sauce'), findsOneWidget);
      expect(find.text('Garlic Bread'), findsNothing);
      expect(service.getMealCalls, 1);

      await pumpWithMutation(
        tester,
        MealComponentAdded(
          mealId: 'meal-1',
          recipeId: 'r3',
          meal: _mealPayload(components: [
            {'recipe_id': 'r1', 'name': 'Spaghetti', 'order_index': 0},
            {'recipe_id': 'r2', 'name': 'Tomato Sauce', 'order_index': 1},
            {'recipe_id': 'r3', 'name': 'Garlic Bread', 'order_index': 2},
          ]),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Spaghetti'), findsOneWidget);
      expect(find.text('Tomato Sauce'), findsOneWidget);
      expect(find.text('Garlic Bread'), findsOneWidget);
      // In-place patch — no second getMeal call.
      expect(service.getMealCalls, 1);
    },
  );

  testWidgets(
    'MealFavorited with meal=null falls back to invalidateSelf → refetch',
    (tester) async {
      await tester.pumpWidget(_harness('meal-1'));
      await tester.pumpAndSettle();
      expect(service.getMealCalls, 1);

      // Server gave us a slim shape — subscribers fall back to
      // invalidate-and-refetch.
      await pumpWithMutation(
        tester,
        const MealFavorited(
          mealId: 'meal-1',
          bookId: 'book-1',
          isFavorited: true,
          meal: null,
        ),
      );
      await tester.pumpAndSettle();

      // One extra fetch — the invalidate-refetch path ran.
      expect(service.getMealCalls, 2);
    },
  );
}
