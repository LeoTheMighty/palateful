// rmc-1 AC #7 — meal-edit mutation failures route through
// `showMutationFailureSnackbar` with the right `MutationType`. Copy is
// keyed by `MutationType.updateMeal` etc., so the visible toast reads
// "Couldn't update meal" instead of the ad-hoc "Could not save meal".

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
  _FakeMealService() : super(_FakeApi());

  final Meal stub = Meal(
    id: 'meal-1',
    name: 'Original',
    recipeBookId: 'book-1',
    createdAt: DateTime.parse('2026-04-18T10:00:00Z'),
    updatedAt: DateTime.parse('2026-04-18T10:00:00Z'),
    components: const [
      MealComponent(recipeId: 'r1', name: 'A', orderIndex: 0),
      MealComponent(recipeId: 'r2', name: 'B', orderIndex: 1),
    ],
  );

  @override
  Future<Meal> getMeal(String mealId) async => stub;

  @override
  Future<Meal> updateMeal(
    String mealId, {
    String? name,
    String? description,
  }) async {
    throw Exception('simulated 500');
  }
}

Widget _harness() {
  final router = GoRouter(
    routes: [
      GoRoute(
        path: '/',
        builder: (_, _) => const MealEditScreen(mealId: 'meal-1'),
      ),
    ],
  );
  return ProviderScope(child: MaterialApp.router(routerConfig: router));
}

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  setUp(() {
    final g = GetIt.instance;
    if (g.isRegistered<MealService>()) g.unregister<MealService>();
    g.registerSingleton<MealService>(_FakeMealService());
  });

  tearDown(() {
    final g = GetIt.instance;
    if (g.isRegistered<MealService>()) g.unregister<MealService>();
  });

  testWidgets('updateMeal failure → "Couldn\'t update meal" snackbar',
      (tester) async {
    await tester.pumpWidget(_harness());
    await tester.pumpAndSettle();

    await tester.tap(find.text('Save'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text("Couldn't update meal"), findsOneWidget);
    expect(find.text('Retry'), findsOneWidget);
  });
}
