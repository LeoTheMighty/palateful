import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/di/injection.dart';
import '../models/meal.dart';
import '../services/meal_service.dart';

/// FutureProvider.family — list of Meals for a given book.
/// Invalidate via `ref.invalidate(mealsByBookProvider(bookId))` after
/// any mutation on a meal inside that book.
final mealsByBookProvider =
    FutureProvider.family<List<MealSummary>, String>((ref, bookId) async {
  return getIt<MealService>().listMealsInBook(bookId);
});

/// Flat list across every readable book — used by the discoverability
/// epic's home grid. Separate provider so callers that only care about
/// a single book don't pay the cross-book list cost.
final mealsAllProvider =
    FutureProvider<List<MealSummary>>((ref) async {
  return getIt<MealService>().listMeals();
});

/// Full Meal detail by id — hydrated components.
final mealByIdProvider =
    FutureProvider.family<Meal, String>((ref, mealId) async {
  return getIt<MealService>().getMeal(mealId);
});

/// Helper: bust both the detail provider and the containing book list
/// after a mutation. Callers usually know the book_id already (they have
/// the Meal in hand); callers that don't should pass `null` and we skip
/// the list invalidation.
///
/// Typed as `dynamic` so both `Ref` (provider-side) and `WidgetRef`
/// (widget-side) can call it; both expose the same `invalidate` signature.
void invalidateMeal(
  dynamic ref,
  String mealId, {
  String? bookId,
}) {
  ref.invalidate(mealByIdProvider(mealId));
  if (bookId != null) {
    ref.invalidate(mealsByBookProvider(bookId));
  }
  ref.invalidate(mealsAllProvider);
}
