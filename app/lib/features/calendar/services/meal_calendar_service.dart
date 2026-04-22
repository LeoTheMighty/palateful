import '../../../core/services/api_client.dart';
import '../models/meal_event.dart';

/// Service for meal calendar CRUD operations.
class MealCalendarService {
  final ApiClient _apiClient;

  MealCalendarService(this._apiClient);

  Future<List<MealEvent>> listMealEvents(
    DateTime start,
    DateTime end, {
    String? calendarId,
  }) async {
    final response = await _apiClient.listMealEventsForRange(
      start,
      end,
      calendarId: calendarId,
    );
    final data = response.data as Map<String, dynamic>;
    final items = (data['items'] as List).cast<Map<String, dynamic>>();
    return items.map(MealEvent.fromJson).toList();
  }

  /// Fetch a single meal event by id. Used by the deep-link
   /// MealDetailScreen — list endpoints return a windowed projection,
   /// the detail endpoint returns the full record (participants etc.).
  Future<MealEvent> getMealEvent(String eventId) async {
    final response = await _apiClient.getMealEvent(eventId);
    return MealEvent.fromJson(response.data as Map<String, dynamic>);
  }

  Future<MealEvent> createMealEvent({
    required String title,
    required DateTime scheduledAt,
    required MealType mealType,
    required String calendarId,
    String? recipeId,
    String? mealId,
    bool isShared = true,
  }) async {
    assert(
      recipeId == null || mealId == null,
      'createMealEvent: recipeId and mealId are mutually exclusive',
    );
    final response = await _apiClient.createMealEvent({
      'title': title,
      'scheduled_at': scheduledAt.toUtc().toIso8601String(),
      'meal_type': mealType.name,
      'calendar_id': calendarId,
      if (recipeId != null) 'recipe_id': recipeId,
      if (mealId != null) 'meal_id': mealId,
      'is_shared': isShared,
    });
    return MealEvent.fromJson(response.data as Map<String, dynamic>);
  }

  Future<MealEvent> updateMealEvent(
    String eventId, {
    required DateTime scheduledAt,
    required MealType mealType,
    String? calendarId,
  }) async {
    final response = await _apiClient.updateMealEvent(eventId, {
      'scheduled_at': scheduledAt.toUtc().toIso8601String(),
      'meal_type': mealType.name,
      if (calendarId != null) 'calendar_id': calendarId,
    });
    return MealEvent.fromJson(response.data as Map<String, dynamic>);
  }

  /// Move-to-calendar — delegates the calendar_id flip to the backend.
  /// Same-calendar is a 200 no-op server-side.
  Future<MealEvent> moveMealEventToCalendar(
    String eventId,
    String newCalendarId,
  ) async {
    final response = await _apiClient.updateMealEvent(eventId, {
      'calendar_id': newCalendarId,
    });
    return MealEvent.fromJson(response.data as Map<String, dynamic>);
  }

  Future<void> deleteMealEvent(String eventId) async {
    await _apiClient.deleteMealEvent(eventId);
  }

  /// Partial-update: writes a new scheduled_at only. Callers derive the UTC
  /// DateTime from a local picker (bugs-cal-1).
  Future<MealEvent> rescheduleMealEvent(String eventId, DateTime scheduledAt) async {
    final response = await _apiClient.updateMealEvent(eventId, {
      'scheduled_at': scheduledAt.toUtc().toIso8601String(),
    });
    return MealEvent.fromJson(response.data as Map<String, dynamic>);
  }

  /// Flip status to `completed`. The backend pantry-decrement hook fires on
  /// the planned→completed transition (see update_meal_event.py).
  Future<void> markMealCompleted(String eventId) async {
    await _apiClient.updateMealEvent(eventId, {'status': 'completed'});
  }

  /// Create a recurrence rule. Server materializes the first 9 weeks in the
  /// same transaction, so the snackbar + reload picks up the new tiles
  /// immediately.
  Future<RecurrenceRule> createRecurrenceRule({
    required MealType mealType,
    required List<String> weekdays,
    required String interval,
    required DateTime startDate,
    required String tzName,
    required String calendarId,
    String? title,
    String? recipeId,
    String? mealId,
    DateTime? endDate,
    String? monthlyNth,
    bool isShared = true,
  }) async {
    assert(
      recipeId == null || mealId == null,
      'createRecurrenceRule: recipeId and mealId are mutually exclusive',
    );
    final data = <String, dynamic>{
      'meal_type': mealType.name,
      'weekdays': weekdays,
      'interval': interval,
      'start_date': startDate.toIso8601String().substring(0, 10),
      'tz_name': tzName,
      'calendar_id': calendarId,
      'is_shared': isShared,
    };
    if (title != null && title.isNotEmpty) data['title'] = title;
    if (recipeId != null) data['recipe_id'] = recipeId;
    if (mealId != null) data['meal_id'] = mealId;
    if (endDate != null) {
      data['end_date'] = endDate.toIso8601String().substring(0, 10);
    }
    if (monthlyNth != null) data['monthly_nth'] = monthlyNth;

    final response = await _apiClient.createRecurrenceRule(data);
    return RecurrenceRule.fromJson(response.data as Map<String, dynamic>);
  }

  Future<List<RecurrenceRule>> listRecurrenceRules() async {
    final response = await _apiClient.listRecurrenceRules();
    final data = response.data as Map<String, dynamic>;
    final items = (data['items'] as List).cast<Map<String, dynamic>>();
    return items.map(RecurrenceRule.fromJson).toList();
  }

  Future<RecurrenceRule> getRecurrenceRule(String ruleId) async {
    final response = await _apiClient.getRecurrenceRule(ruleId);
    return RecurrenceRule.fromJson(response.data as Map<String, dynamic>);
  }

  Future<void> deleteRecurrenceRule(
    String ruleId, {
    String scope = 'series',
    DateTime? occurrenceDate,
  }) async {
    await _apiClient.deleteRecurrenceRule(
      ruleId,
      scope: scope,
      occurrenceDate:
          occurrenceDate?.toIso8601String().substring(0, 10),
    );
  }

  Future<Map<String, dynamic>> updateRecurrenceRule(
    String ruleId, {
    required String scope,
    DateTime? occurrenceDate,
    String? title,
    String? recipeId,
    String? mealType,
    List<String>? weekdays,
    String? interval,
    String? monthlyNth,
    DateTime? endDate,
    bool clearEndDate = false,
    bool? isShared,
    String? tzName,
    String? calendarId,
  }) async {
    final data = <String, dynamic>{'scope': scope};
    if (occurrenceDate != null) {
      data['occurrence_date'] =
          occurrenceDate.toIso8601String().substring(0, 10);
    }
    if (title != null) data['title'] = title;
    if (recipeId != null) data['recipe_id'] = recipeId;
    if (mealType != null) data['meal_type'] = mealType;
    if (weekdays != null) data['weekdays'] = weekdays;
    if (interval != null) data['interval'] = interval;
    if (monthlyNth != null) data['monthly_nth'] = monthlyNth;
    if (endDate != null) {
      data['end_date'] = endDate.toIso8601String().substring(0, 10);
    } else if (clearEndDate) {
      data['end_date'] = null;
    }
    if (isShared != null) data['is_shared'] = isShared;
    if (tzName != null) data['tz_name'] = tzName;
    if (calendarId != null) data['calendar_id'] = calendarId;

    final response = await _apiClient.updateRecurrenceRule(ruleId, data);
    return response.data as Map<String, dynamic>;
  }

  /// Rule-level Move-to-calendar. Cascades to future materialized events.
  Future<void> moveRecurrenceRuleToCalendar(
    String ruleId,
    String newCalendarId,
  ) async {
    await updateRecurrenceRule(
      ruleId,
      scope: 'all',
      calendarId: newCalendarId,
    );
  }
}
