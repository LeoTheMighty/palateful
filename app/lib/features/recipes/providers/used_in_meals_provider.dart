import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/di/injection.dart';
import '../../../core/state/mutation_bus.dart';
import '../../meals/models/meal.dart';
import '../../meals/services/meal_service.dart';

/// rmc-2: family-keyed list of Meals that reference [recipeId].
///
/// Fed by `MealService.listMealsUsingRecipe`. Subscribes to the
/// MutationBus and invalidates on:
///   - `MealComponentAdded | MealComponentRemoved` with
///     `event.recipeId == recipeId` — the narrow path (zero-noise).
///   - `MealArchived | MealUnarchived | MealUpdated` — no recipe filter,
///     coalesced with a 100ms debounce because any referenced meal's
///     summary could change its name / archive flag and the cross-lookup
///     result is derived.
///
/// `autoDispose` because this list is only mounted on the recipe detail
/// screen — unmounting tears the subscription down cleanly.
final usedInMealsProvider =
    FutureProvider.family.autoDispose<List<MealSummary>?, String>(
  (ref, recipeId) async {
    Timer? debounce;
    final sub = ref.read(mutationBusProvider).listen((event) {
      if (_narrowMatch(event, recipeId)) {
        debounce?.cancel();
        debounce = null;
        ref.invalidateSelf();
        return;
      }
      if (!_coarseMatch(event)) return;
      debounce?.cancel();
      debounce = Timer(const Duration(milliseconds: 100), () {
        debounce = null;
        ref.invalidateSelf();
      });
    });
    ref.onDispose(() {
      debounce?.cancel();
      sub.cancel();
    });

    try {
      return await getIt<MealService>().listMealsUsingRecipe(recipeId);
    } catch (_) {
      // Failure is silent — recipe detail must render even if the cross
      // lookup explodes. Returning `null` keeps the widget in its
      // `SizedBox.shrink()` branch (md-6 load-bearing invariant).
      return null;
    }
  },
);

bool _narrowMatch(MutationEvent event, String recipeId) {
  return switch (event) {
    MealComponentAdded(recipeId: final r) ||
    MealComponentRemoved(recipeId: final r) =>
      r == recipeId,
    _ => false,
  };
}

bool _coarseMatch(MutationEvent event) {
  return switch (event) {
    MealArchived() || MealUnarchived() || MealUpdated() => true,
    _ => false,
  };
}
