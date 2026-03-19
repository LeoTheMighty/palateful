import '../../../core/services/api_client.dart';
import '../models/meal_event.dart';

/// Service for meal calendar CRUD operations.
class MealCalendarService {
  final ApiClient _apiClient;

  MealCalendarService(this._apiClient);

  Future<List<MealEvent>> listMealEvents(DateTime start, DateTime end) async {
    final response = await _apiClient.listMealEventsForRange(start, end);
    final data = response.data as Map<String, dynamic>;
    final items = (data['items'] as List).cast<Map<String, dynamic>>();
    return items.map(MealEvent.fromJson).toList();
  }

  Future<MealEvent> createMealEvent({
    required String title,
    required DateTime scheduledAt,
    required MealType mealType,
    String? recipeId,
    bool isShared = true,
  }) async {
    final response = await _apiClient.createMealEvent({
      'title': title,
      'scheduled_at': scheduledAt.toUtc().toIso8601String(),
      'meal_type': mealType.name,
      if (recipeId != null) 'recipe_id': recipeId,
      'is_shared': isShared,
    });
    return MealEvent.fromJson(response.data as Map<String, dynamic>);
  }

  Future<MealEvent> updateMealEvent(
    String eventId, {
    required DateTime scheduledAt,
    required MealType mealType,
  }) async {
    final response = await _apiClient.updateMealEvent(eventId, {
      'scheduled_at': scheduledAt.toUtc().toIso8601String(),
      'meal_type': mealType.name,
    });
    return MealEvent.fromJson(response.data as Map<String, dynamic>);
  }

  Future<void> deleteMealEvent(String eventId) async {
    await _apiClient.deleteMealEvent(eventId);
  }
}
