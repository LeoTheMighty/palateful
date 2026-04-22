import '../../../core/services/api_client.dart';
import '../../../core/state/mutation_bus.dart';

/// Service wrapper around recipe mutations. Every mutation method emits
/// on the [mutationBusProvider] **before** returning to the caller, on
/// the success branch of the API call — Locked Decision #1 in the
/// reactive-foundation epic.
///
/// UI handlers await the service method and handle thrown errors with
/// `showMutationFailureSnackbar`; they do NOT emit directly.
class RecipeService {
  RecipeService(this._api);

  final ApiClient _api;

  /// Create a recipe in [bookId] from [data]. On 200 emits
  /// [RecipeCreated] with the full server payload. Returns the created
  /// recipe map.
  Future<Map<String, dynamic>> createRecipe(
    String bookId,
    Map<String, dynamic> data,
  ) async {
    final response = await _api.createRecipe(bookId, data);
    final recipe = _asMap(response.data);
    emitMutation(RecipeCreated(
      recipeId: recipe['id']?.toString() ?? '',
      recipe: recipe,
      bookId: bookId,
    ));
    return recipe;
  }

  /// Update recipe fields. Emits [RecipeUpdated] on success.
  Future<Map<String, dynamic>> updateRecipe(
    String recipeId,
    Map<String, dynamic> data,
  ) async {
    final response = await _api.updateRecipe(recipeId, data);
    final recipe = _asMap(response.data);
    emitMutation(RecipeUpdated(recipeId: recipeId, recipe: recipe));
    return recipe;
  }

  /// Soft-delete (a.k.a. archive) a recipe. Emits [RecipeArchived].
  /// [bookId] carries the source book so Home/book surfaces can scope
  /// their invalidation.
  Future<void> archiveRecipe(
    String recipeId, {
    required String bookId,
  }) async {
    await _api.deleteRecipe(recipeId);
    emitMutation(RecipeArchived(recipeId: recipeId, bookId: bookId));
  }

  /// Restore a previously-archived recipe. Emits [RecipeUnarchived]
  /// with the refreshed payload.
  Future<Map<String, dynamic>> restoreRecipe(String recipeId) async {
    final response = await _api.restoreRecipe(recipeId);
    final recipe = _asMap(response.data);
    emitMutation(RecipeUnarchived(recipeId: recipeId, recipe: recipe));
    return recipe;
  }

  /// Toggle favorite. Post rf-2 the server returns the full
  /// `GetRecipe.Response`; pre-rf-2 fallback hands back just
  /// `{is_favorite: bool}` and the caller still gets a consistent event
  /// shape (the `recipe` field is the minimum `{id, is_favorite}`).
  Future<Map<String, dynamic>> toggleFavorite(String recipeId) async {
    final response = await _api.toggleFavorite(recipeId);
    final payload = _asMap(response.data);
    final isFavorited = payload['is_favorite'] == true;
    final recipe = payload.containsKey('name')
        ? payload
        : <String, dynamic>{'id': recipeId, 'is_favorite': isFavorited};
    emitMutation(RecipeFavorited(
      recipeId: recipeId,
      recipe: recipe,
      isFavorited: isFavorited,
    ));
    return recipe;
  }

  /// Fork [recipeId] into [destinationBookId]. Emits [RecipeForked] with
  /// the new (child) recipe payload.
  Future<Map<String, dynamic>> forkRecipe(
    String recipeId,
    String destinationBookId,
  ) async {
    final response = await _api.forkRecipe(recipeId, destinationBookId);
    final recipe = _asMap(response.data);
    emitMutation(RecipeForked(
      recipeId: recipe['id']?.toString() ?? '',
      recipe: recipe,
      parentRecipeId: recipeId,
    ));
    return recipe;
  }

  /// Move [recipeId] from [oldBookId] to [destinationBookId]. Emits
  /// [RecipeMoved] with both book ids so subscribers on either book
  /// surface invalidate.
  Future<Map<String, dynamic>> moveRecipe(
    String recipeId,
    String destinationBookId, {
    required String oldBookId,
  }) async {
    final response = await _api.moveRecipe(recipeId, destinationBookId);
    final recipe = _asMap(response.data);
    emitMutation(RecipeMoved(
      recipeId: recipeId,
      recipe: recipe,
      oldBookId: oldBookId,
      newBookId: destinationBookId,
    ));
    return recipe;
  }

  /// Copy [recipeId] to [destinationBookId]. The backend creates a new
  /// recipe, so this is a [RecipeCreated] in the destination book from
  /// the bus's vantage point.
  Future<Map<String, dynamic>> copyRecipe(
    String recipeId,
    String destinationBookId,
  ) async {
    final response = await _api.copyRecipe(recipeId, destinationBookId);
    final recipe = _asMap(response.data);
    emitMutation(RecipeCreated(
      recipeId: recipe['id']?.toString() ?? '',
      recipe: recipe,
      bookId: destinationBookId,
    ));
    return recipe;
  }

  /// Bulk-archive. Emits exactly ONE [RecipeBulkArchived] event —
  /// Locked Decision #3 (bulk events, not N per-item events).
  Future<void> bulkArchiveRecipes(
    List<String> recipeIds, {
    required String bookId,
  }) async {
    await _api.bulkArchiveRecipes(recipeIds);
    emitMutation(RecipeBulkArchived(recipeIds: recipeIds, bookId: bookId));
  }

  /// Add a free-form note. Emits [RecipeUpdated] — the note lives on
  /// the recipe resource, so a refetch is the simplest reconciliation.
  Future<Map<String, dynamic>> addRecipeNote(
    String recipeId,
    String body,
  ) async {
    final response = await _api.addRecipeNote(recipeId, body);
    final note = _asMap(response.data);
    emitMutation(RecipeUpdated(
      recipeId: recipeId,
      recipe: {'id': recipeId, 'note_added': note},
    ));
    return note;
  }

  /// Delete a note. Emits [RecipeUpdated] — same reasoning as
  /// [addRecipeNote].
  Future<void> deleteRecipeNote(String recipeId, String noteId) async {
    await _api.deleteRecipeNote(recipeId, noteId);
    emitMutation(RecipeUpdated(
      recipeId: recipeId,
      recipe: {'id': recipeId, 'note_deleted': noteId},
    ));
  }

  static Map<String, dynamic> _asMap(Object? data) {
    if (data is Map) return Map<String, dynamic>.from(data);
    return const <String, dynamic>{};
  }
}
