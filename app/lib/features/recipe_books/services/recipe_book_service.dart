import '../../../core/services/api_client.dart';
import '../../../core/state/mutation_bus.dart';

/// Service wrapper around recipe-book mutations.
///
/// Before rp-1 every book mutation was a raw `_apiClient.*` call inside
/// an `_RecipeBookDetailScreenState` / `_RecipeBooksScreenState` / ...
/// `setState` closure, so other surfaces watching the same data could
/// only reconcile on pull-to-refresh. This service owns those calls
/// now, and emits on the [mutationBusProvider] on the success branch of
/// each mutation — Locked Decision #1 in the reactive-foundation epic.
///
/// UI handlers await the service method and route failures through
/// `showMutationFailureSnackbar`; they do NOT emit directly.
class RecipeBookService {
  RecipeBookService(this._api);

  final ApiClient _api;

  // ── Reads ──────────────────────────────────────────────────────────────

  Future<List<Map<String, dynamic>>> listRecipeBooks({
    int limit = 20,
    int offset = 0,
  }) async {
    final response = await _api.getRecipeBooks(limit: limit, offset: offset);
    return _asItems(response.data, key: 'items');
  }

  Future<List<Map<String, dynamic>>> listArchivedRecipeBooks() async {
    final response = await _api.getArchivedRecipeBooks();
    return _asItems(response.data, key: 'items');
  }

  Future<Map<String, dynamic>> getRecipeBook(String id) async {
    final response = await _api.getRecipeBook(id);
    return _asMap(response.data);
  }

  // ── Mutations ──────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> createRecipeBook(
    Map<String, dynamic> data,
  ) async {
    final response = await _api.createRecipeBook(data);
    final book = _asMap(response.data);
    emitMutation(RecipeBookCreated(
      bookId: book['id']?.toString() ?? '',
      book: book,
    ));
    return book;
  }

  /// Generic field update — rename + description / color changes + any
  /// other `PUT /v1/recipe-books/{id}` surface. Emits [RecipeBookUpdated]
  /// with the full server response.
  Future<Map<String, dynamic>> updateRecipeBook(
    String id,
    Map<String, dynamic> data,
  ) async {
    final response = await _api.updateRecipeBook(id, data);
    final book = _asMap(response.data);
    emitMutation(RecipeBookUpdated(bookId: id, book: book));
    return book;
  }

  /// Archive returns `{success, restored_default_recipe_book_id}`. The
  /// optional `restored_default_recipe_book_id` is the id the server
  /// auto-swapped in as the user's default if this book *was* the
  /// default; subscribers (AuthService, HomeScreen) use it to patch
  /// state without a second round-trip.
  Future<String?> archiveRecipeBook(String id) async {
    final response = await _api.archiveRecipeBook(id);
    final data = _asMap(response.data);
    final restoredDefault = data['restored_default_recipe_book_id'] as String?;
    emitMutation(RecipeBookArchived(
      bookId: id,
      restoredDefaultBookId: restoredDefault,
    ));
    return restoredDefault;
  }

  Future<Map<String, dynamic>?> restoreRecipeBook(String id) async {
    final response = await _api.restoreRecipeBook(id);
    final data = _asMap(response.data);
    // Endpoint shape is slim `{success: true}` on some deploys and a
    // full book on others. Null-safe event payload mirrors that.
    final book = data.containsKey('id') ? data : null;
    emitMutation(RecipeBookUnarchived(bookId: id, book: book));
    return book;
  }

  Future<void> deleteRecipeBook(String id) async {
    await _api.deleteRecipeBook(id);
    emitMutation(RecipeBookDeleted(bookId: id));
  }

  Future<Map<String, dynamic>> addMember(
    String bookId, {
    required String userEmail,
    String role = 'editor',
  }) async {
    final response = await _api.addRecipeBookMember(bookId, {
      'email': userEmail,
      'role': role,
    });
    final member = _asMap(response.data);
    final userId = member['user_id']?.toString() ??
        member['id']?.toString() ??
        '';
    emitMutation(RecipeBookMemberAdded(
      bookId: bookId,
      userId: userId,
      role: (member['role'] as String?) ?? role,
    ));
    return member;
  }

  Future<Map<String, dynamic>> updateMemberRole(
    String bookId,
    String userId,
    String role,
  ) async {
    final response = await _api.updateRecipeBookMemberRole(
      bookId,
      userId,
      {'role': role},
    );
    final member = _asMap(response.data);
    emitMutation(RecipeBookMemberChanged(
      bookId: bookId,
      userId: userId,
      newRole: (member['role'] as String?) ?? role,
    ));
    return member;
  }

  Future<void> removeMember(String bookId, String userId) async {
    await _api.removeRecipeBookMember(bookId, userId);
    emitMutation(RecipeBookMemberChanged(
      bookId: bookId,
      userId: userId,
      newRole: null,
    ));
  }

  // ── Bulk recipe operations that live on the book surface ──────────────

  /// Move [recipeIds] to [destinationBookId]. Emits a single
  /// [RecipeMoved] per recipe — the underlying endpoint is a bulk call,
  /// but subscribers already handle the per-item event, so we fan out
  /// one event per id. Destination book provider will invalidate once
  /// per event (MutationEventCoalescer keeps it to one refetch).
  Future<void> bulkMoveRecipes(
    List<String> recipeIds,
    String destinationBookId, {
    required String sourceBookId,
  }) async {
    await _api.bulkMoveRecipes(recipeIds, destinationBookId);
    for (final recipeId in recipeIds) {
      emitMutation(RecipeMoved(
        recipeId: recipeId,
        recipe: {'id': recipeId, 'recipe_book_id': destinationBookId},
        oldBookId: sourceBookId,
        newBookId: destinationBookId,
      ));
    }
  }

  /// Bulk-archive. Emits ONE [RecipeBulkArchived] event — Locked
  /// Decision #3 (bulk events, not N per-item events).
  Future<void> bulkArchiveRecipes(
    List<String> recipeIds, {
    required String bookId,
  }) async {
    await _api.bulkArchiveRecipes(recipeIds);
    emitMutation(RecipeBulkArchived(recipeIds: recipeIds, bookId: bookId));
  }

  Future<void> bulkUpdateTags(
    List<String> recipeIds, {
    List<String>? addTags,
    List<String>? removeTags,
  }) async {
    await _api.bulkUpdateTags(
      recipeIds,
      addTags: addTags,
      removeTags: removeTags,
    );
    // Tag changes manifest as RecipeUpdated per recipe — subscribers
    // already know to refetch on that type.
    for (final recipeId in recipeIds) {
      emitMutation(RecipeUpdated(
        recipeId: recipeId,
        recipe: {'id': recipeId},
      ));
    }
  }

  // ── Helpers ────────────────────────────────────────────────────────────

  static Map<String, dynamic> _asMap(Object? data) {
    if (data is Map) return Map<String, dynamic>.from(data);
    return const <String, dynamic>{};
  }

  static List<Map<String, dynamic>> _asItems(
    Object? data, {
    required String key,
  }) {
    if (data is Map) {
      final items = data[key];
      if (items is List) {
        return items
            .whereType<Map>()
            .map((m) => Map<String, dynamic>.from(m))
            .toList();
      }
    }
    if (data is List) {
      return data
          .whereType<Map>()
          .map((m) => Map<String, dynamic>.from(m))
          .toList();
    }
    return const <Map<String, dynamic>>[];
  }
}
