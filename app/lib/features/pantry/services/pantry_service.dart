import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../../../core/state/mutation_bus.dart';
import '../models/pantry.dart';
import '../models/pantry_ingredient.dart';

/// rp-3 — stateless PantryService. Pre-rp-3 the service kept a
/// `Pantry?` cache behind a `StreamController<Pantry?>` which violated
/// Foundation Locked Decision #9. Now every read goes straight to the
/// API and every mutation emits on the MutationBus.
///
/// The `pantryIngredientsProvider(pantryId)` family (see
/// `providers/pantry_provider.dart`) owns list-state and subscribes to
/// `PantryItem*` events with a pantry-id filter.
class PantryService {
  PantryService({ApiClient? api}) : _api = api ?? getIt<ApiClient>();

  final ApiClient _api;

  Future<Pantry> getDefaultPantry() async {
    final response = await _api.getDefaultPantry();
    return Pantry.fromJson(response.data as Map<String, dynamic>);
  }

  Future<PantryIngredient> addPantryIngredient(
    String pantryId,
    Map<String, dynamic> data,
  ) async {
    final response = await _api.addPantryIngredient(pantryId, data);
    final added =
        PantryIngredient.fromJson(response.data as Map<String, dynamic>);
    emitMutation(PantryItemAdded(
      itemId: added.ingredientId,
      item: response.data as Map<String, dynamic>,
      pantryId: pantryId,
    ));
    return added;
  }

  Future<PantryIngredient> updatePantryIngredient(
    String pantryId,
    String ingredientId,
    Map<String, dynamic> data,
  ) async {
    final response =
        await _api.updatePantryIngredient(pantryId, ingredientId, data);
    final updated =
        PantryIngredient.fromJson(response.data as Map<String, dynamic>);
    emitMutation(PantryItemUpdated(
      itemId: ingredientId,
      item: response.data as Map<String, dynamic>,
      pantryId: pantryId,
    ));
    return updated;
  }

  Future<void> deletePantryIngredient(
    String pantryId,
    String ingredientId,
  ) async {
    await _api.deletePantryIngredient(pantryId, ingredientId);
    emitMutation(PantryItemRemoved(
      itemId: ingredientId,
      pantryId: pantryId,
    ));
  }
}
