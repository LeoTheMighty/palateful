import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/calendar/widgets/meal_autocomplete_field.dart';
import 'package:palateful/features/meals/models/meal.dart';
import 'package:palateful/features/meals/services/meal_service.dart';

/// Minimal fake MealService that exposes only the autocomplete path; all
/// other methods deliberately throw so the suite surfaces unintended use.
class _FakeMealService implements MealService {
  int searchCalls = 0;
  String? lastQuery;
  int? lastLimit;
  List<MealSummary> results = const [];

  @override
  Future<List<MealSummary>> searchMeals(String query, {int limit = 8}) async {
    searchCalls++;
    lastQuery = query;
    lastLimit = limit;
    return results;
  }

  @override
  Future<MealAddToShoppingListResult> addToShoppingList(
          String mealId, String shoppingListId) async =>
      throw UnimplementedError();

  @override
  Future<List<MealSummary>> listMealsInBook(String bookId,
          {int limit = 50,
          int offset = 0,
          bool includeArchived = false}) async =>
      throw UnimplementedError();

  @override
  Future<List<MealSummary>> listMeals(
          {int? limit,
          int offset = 0,
          bool includeArchived = false,
          bool? archived,
          String? scope}) async =>
      throw UnimplementedError();

  @override
  Future<List<MealSummary>> listMealsUsingRecipe(String recipeId) async =>
      throw UnimplementedError();

  @override
  Future<Meal> getMeal(String mealId) async => throw UnimplementedError();

  @override
  Future<Meal> createMeal(
          {required String bookId,
          required String name,
          String? description,
          required List<String> componentRecipeIds}) async =>
      throw UnimplementedError();

  @override
  Future<Meal> updateMeal(String mealId,
          {String? name, String? description}) async =>
      throw UnimplementedError();

  @override
  Future<Meal> addRecipeToMeal(String mealId,
          {required String recipeId, int? orderIndex}) async =>
      throw UnimplementedError();

  @override
  Future<Meal> removeRecipeFromMeal(String mealId, String recipeId) async =>
      throw UnimplementedError();

  @override
  Future<Meal> reorderMealComponents(
          String mealId, List<String> recipeIds) async =>
      throw UnimplementedError();

  @override
  Future<void> archiveMeal(String mealId, {required String bookId}) async =>
      throw UnimplementedError();

  @override
  Future<void> restoreMeal(String mealId, {required String bookId}) async =>
      throw UnimplementedError();

  @override
  Future<bool> favoriteMeal(String mealId, {required String bookId}) async =>
      throw UnimplementedError();

  @override
  Future<bool> unfavoriteMeal(String mealId, {required String bookId}) async =>
      throw UnimplementedError();

  @override
  Future<ShareMealResult> share(String mealId) async =>
      throw UnimplementedError();

  @override
  Future<PublicMealDto> getPublicMealByToken(String token) async =>
      throw UnimplementedError();
}

Widget _host(Widget child) =>
    MaterialApp(home: Scaffold(body: Padding(padding: const EdgeInsets.all(16), child: child)));

MealSummary _summary(String id, String name, int count) => MealSummary(
      id: id,
      name: name,
      recipeBookId: 'book-1',
      componentCount: count,
      updatedAt: DateTime.now(),
    );

void main() {
  testWidgets('debounces 300ms then calls searchMeals and renders results',
      (tester) async {
    final svc = _FakeMealService();
    svc.results = [_summary('m1', 'Kale Salad Meal', 2)];
    MealPick? picked;

    await tester.pumpWidget(_host(
      MealAutocompleteField(
        mealService: svc,
        onPicked: (p) => picked = p,
      ),
    ));

    await tester.enterText(find.byType(TextField), 'Kale');
    // Before debounce window elapses, no call.
    await tester.pump(const Duration(milliseconds: 150));
    expect(svc.searchCalls, 0);

    await tester.pump(const Duration(milliseconds: 200));
    expect(svc.searchCalls, 1);
    expect(svc.lastQuery, 'Kale');
    expect(svc.lastLimit, 8);

    // Results render with the canonical component-count label.
    await tester.pump();
    expect(find.text('Kale Salad Meal'), findsOneWidget);
    expect(find.text('2 recipes'), findsOneWidget);

    await tester.tap(find.text('Kale Salad Meal'));
    await tester.pump();
    expect(picked?.mealId, 'm1');
    expect(picked?.name, 'Kale Salad Meal');
    expect(picked?.componentCount, 2);
    expect(
      find.textContaining('Linked to Kale Salad Meal'),
      findsAtLeastNWidgets(1),
    );
  });

  testWidgets('initialMeal seeds the linked chip without a network call',
      (tester) async {
    final svc = _FakeMealService();

    await tester.pumpWidget(_host(
      MealAutocompleteField(
        mealService: svc,
        onPicked: (_) {},
        initialMeal: const MealPick(
          mealId: 'm-seed',
          name: 'Seeded Meal',
          componentCount: 3,
        ),
      ),
    ));
    await tester.pump();

    expect(
      find.textContaining('Linked to Seeded Meal'),
      findsAtLeastNWidgets(1),
    );
    expect(svc.searchCalls, 0);
  });

  testWidgets('no-match renders empty-state copy (no free-text fallback)',
      (tester) async {
    final svc = _FakeMealService(); // empty results
    await tester.pumpWidget(_host(
      MealAutocompleteField(
        mealService: svc,
        onPicked: (_) {},
      ),
    ));

    await tester.enterText(find.byType(TextField), 'zzzzz');
    await tester.pump(const Duration(milliseconds: 350));
    await tester.pump();

    expect(find.textContaining('No meals match'), findsOneWidget);
  });
}
