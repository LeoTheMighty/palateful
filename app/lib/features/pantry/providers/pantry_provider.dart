import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/di/injection.dart';
import '../../../core/state/mutation_bus.dart';
import '../models/pantry.dart';
import '../models/pantry_ingredient.dart';
import '../services/pantry_service.dart';

/// rp-3 — the signed-in user's default pantry (meta + ingredients).
/// The backend returns both in one fetch, so this provider owns the
/// whole fetch. `pantryIngredientsProvider(pantryId)` is a convenience
/// selector over this same fetch, family-keyed so multiple screens
/// can key off a specific pantry id (future pantry-per-book support).
final defaultPantryProvider =
    FutureProvider.autoDispose<Pantry>((ref) async {
  ref.keepAlive();
  final sub = ref.read(mutationBusProvider).listen((event) {
    if (_isPantryEvent(event)) ref.invalidateSelf();
  });
  ref.onDispose(sub.cancel);

  return getIt<PantryService>().getDefaultPantry();
});

/// Family-keyed list of ingredients in [pantryId]. Subscribes to
/// `PantryItem*` events filtered by `event.pantryId == pantryId`.
final pantryIngredientsProvider =
    FutureProvider.autoDispose.family<List<PantryIngredient>, String>(
  (ref, pantryId) async {
    ref.keepAlive();
    final sub = ref.read(mutationBusProvider).listen((event) {
      if (_isPantryEventForId(event, pantryId)) ref.invalidateSelf();
    });
    ref.onDispose(sub.cancel);

    // Read the same underlying fetch used by `defaultPantryProvider`.
    // If the pantryId is the default, this shares the cache; otherwise
    // we'd pivot to a per-id API call (out-of-scope for rp-3; default
    // pantry is the only surface today).
    final pantry = await getIt<PantryService>().getDefaultPantry();
    if (pantry.id != pantryId) return const <PantryIngredient>[];
    return pantry.items;
  },
);

bool _isPantryEvent(MutationEvent event) =>
    event is PantryItemAdded ||
    event is PantryItemUpdated ||
    event is PantryItemRemoved;

bool _isPantryEventForId(MutationEvent event, String pantryId) {
  if (event is PantryItemAdded) return event.pantryId == pantryId;
  if (event is PantryItemUpdated) return event.pantryId == pantryId;
  if (event is PantryItemRemoved) return event.pantryId == pantryId;
  return false;
}
