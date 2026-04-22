import '../../../core/services/api_client.dart';
import '../../../core/state/mutation_bus.dart';

/// rp-3 — CookingLog handoff from the meals/calendar epic. Wraps
/// `POST /v1/cooking-logs` and emits [CookingLogCreated] on success so
/// the recipe-detail cooking-history section can refetch without a
/// pull-to-refresh.
class CookingLogService {
  CookingLogService(this._api);

  final ApiClient _api;

  /// Create a cooking-log row for [recipeId]. The backend also fans
  /// out to meal-level logs when `meal_event_id` is present; we only
  /// emit a single [CookingLogCreated] keyed by [recipeId] — Locked
  /// Decision #3 (bulk/fan-out events are owned by the server-side
  /// broadcast, not the client-side service).
  Future<Map<String, dynamic>> create(
    String recipeId,
    Map<String, dynamic> feedback,
  ) async {
    final response = await _api.createCookingLog({
      'recipe_id': recipeId,
      ...feedback,
    });
    final log = _asMap(response.data);
    emitMutation(CookingLogCreated(
      logId: log['id']?.toString() ?? '',
      log: log,
      recipeId: recipeId,
    ));
    return log;
  }

  Future<List<Map<String, dynamic>>> listForRecipe(String recipeId) async {
    final response = await _api.getRecipeCookingLogs(recipeId);
    final data = response.data;
    if (data is Map) {
      final items = data['items'];
      if (items is List) {
        return items
            .whereType<Map>()
            .map((m) => Map<String, dynamic>.from(m))
            .toList();
      }
    }
    return const <Map<String, dynamic>>[];
  }

  static Map<String, dynamic> _asMap(Object? data) {
    if (data is Map) return Map<String, dynamic>.from(data);
    return const <String, dynamic>{};
  }
}
