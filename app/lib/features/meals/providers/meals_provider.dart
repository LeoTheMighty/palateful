import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/di/injection.dart';
import '../../../core/state/mutation_bus.dart';
import '../models/meal.dart';
import '../services/meal_service.dart';

/// FutureProvider.family — list of Meals for a given book.
///
/// Subscribes to [mutationBusProvider] and refetches on any meal event
/// scoped to [bookId]. rmc-1 convention: filter by `event.bookId ==
/// bookId` before calling `ref.invalidateSelf()` so an edit in book A
/// doesn't thrash book B's list.
final mealsByBookProvider =
    FutureProvider.family<List<MealSummary>, String>((ref, bookId) async {
  final sub = ref.read(mutationBusProvider).listen((event) {
    if (_mealsByBookShouldInvalidate(event, bookId)) {
      ref.invalidateSelf();
    }
  });
  ref.onDispose(sub.cancel);
  return getIt<MealService>().listMealsInBook(bookId);
});

/// Flat list across every readable book — used by the discoverability
/// epic's home grid. Separate provider so callers that only care about
/// a single book don't pay the cross-book list cost.
///
/// Subscribes to the same meal event union as [mealsByBookProvider] but
/// without the book-id filter (every meal mutation anywhere could
/// affect the flat list).
final mealsAllProvider =
    FutureProvider<List<MealSummary>>((ref) async {
  final sub = ref.read(mutationBusProvider).listen((event) {
    if (_mealsAllShouldInvalidate(event)) {
      ref.invalidateSelf();
    }
  });
  ref.onDispose(sub.cancel);
  return getIt<MealService>().listMeals();
});

/// Full Meal detail by id — hydrated components.
///
/// Implemented as an [AsyncNotifier] family (rather than
/// `FutureProvider.family`) so the mutation-bus listener can patch
/// state in place via `state = AsyncData(...)` on payload-bearing
/// events — avoiding a refetch round-trip per rmc-1 AC #5. On events
/// without a full Meal payload (e.g. `MealFavorited` with `meal ==
/// null`), falls back to `ref.invalidateSelf()`.
class MealByIdNotifier extends AsyncNotifier<Meal> {
  MealByIdNotifier(this.mealId);

  final String mealId;

  @override
  Future<Meal> build() async {
    final sub = ref.read(mutationBusProvider).listen(_handleEvent);
    ref.onDispose(sub.cancel);
    return getIt<MealService>().getMeal(mealId);
  }

  void _handleEvent(MutationEvent event) {
    // Narrow by meal id first to avoid parsing payloads we don't care
    // about. Each branch either patches in place (full-Meal payload) or
    // falls back to invalidate (slim / id-only).
    switch (event) {
      case MealUpdated() when event.mealId == mealId:
        state = AsyncData(Meal.fromJson(event.meal));
      case MealComponentAdded() when event.mealId == mealId:
        state = AsyncData(Meal.fromJson(event.meal));
      case MealComponentRemoved() when event.mealId == mealId:
        state = AsyncData(Meal.fromJson(event.meal));
      case MealComponentsReordered() when event.mealId == mealId:
        state = AsyncData(Meal.fromJson(event.meal));
      case MealFavorited() when event.mealId == mealId:
        final payload = event.meal;
        if (payload != null) {
          state = AsyncData(Meal.fromJson(payload));
        } else {
          ref.invalidateSelf();
        }
      case MealUnarchived() when event.mealId == mealId:
        final payload = event.meal;
        if (payload != null) {
          state = AsyncData(Meal.fromJson(payload));
        } else {
          ref.invalidateSelf();
        }
      case MealArchived() when event.mealId == mealId:
        // Archived meals drop their cached state; next read returns
        // the archived Meal (`archived_at` populated).
        ref.invalidateSelf();
      default:
        // Not for us.
        break;
    }
  }
}

final mealByIdProvider =
    AsyncNotifierProvider.family<MealByIdNotifier, Meal, String>(
  MealByIdNotifier.new,
);

/// Helper: bust both the detail provider and the containing book list
/// after a mutation. Callers usually know the book_id already (they have
/// the Meal in hand); callers that don't should pass `null` and we skip
/// the list invalidation.
///
/// Typed as `dynamic` so both `Ref` (provider-side) and `WidgetRef`
/// (widget-side) can call it; both expose the same `invalidate` signature.
///
/// **Deprecated** — kept as a one-release shim per rmc-1 AC #6.
/// `MealService` now emits MutationBus events on every mutation, and
/// the providers subscribe and refetch themselves. Call sites in
/// `meal_edit_screen.dart` / `meal_detail_screen.dart` pass through
/// unchanged; the shim is a no-op from the provider's perspective but
/// still needed for backward compatibility until those call sites are
/// removed.
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

bool _mealsByBookShouldInvalidate(MutationEvent event, String bookId) {
  return switch (event) {
    MealCreated(bookId: final b) ||
    MealArchived(bookId: final b) ||
    MealUnarchived(bookId: final b) ||
    MealFavorited(bookId: final b) =>
      b == bookId,
    // Component + update events don't carry bookId but could affect
    // summary fields (name, component count, thumbnails) in the list.
    // Invalidate unconditionally — cheap for a single book.
    MealUpdated() ||
    MealComponentAdded() ||
    MealComponentRemoved() ||
    MealComponentsReordered() =>
      true,
    _ => false,
  };
}

bool _mealsAllShouldInvalidate(MutationEvent event) {
  return switch (event) {
    MealCreated() ||
    MealUpdated() ||
    MealArchived() ||
    MealUnarchived() ||
    MealFavorited() ||
    MealComponentAdded() ||
    MealComponentRemoved() ||
    MealComponentsReordered() =>
      true,
    _ => false,
  };
}
