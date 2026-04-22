// Meal event models for the calendar feature.

enum MealType {
  breakfast,
  lunch,
  dinner,
  snack;

  String get displayName {
    switch (this) {
      case MealType.breakfast:
        return 'Breakfast';
      case MealType.lunch:
        return 'Lunch';
      case MealType.dinner:
        return 'Dinner';
      case MealType.snack:
        return 'Snack';
    }
  }

  static MealType fromString(String value) {
    return MealType.values.firstWhere(
      (m) => m.name == value,
      orElse: () => MealType.dinner,
    );
  }
}

class RecipeSummary {
  final String id;
  final String name;
  final String? imageUrl;
  final int? prepTime;
  final int? cookTime;

  const RecipeSummary({
    required this.id,
    required this.name,
    this.imageUrl,
    this.prepTime,
    this.cookTime,
  });

  /// Total prep + cook time in minutes, or null if both are absent/zero.
  int? get totalMinutes {
    final total = (prepTime ?? 0) + (cookTime ?? 0);
    return total > 0 ? total : null;
  }

  factory RecipeSummary.fromJson(Map<String, dynamic> json) {
    return RecipeSummary(
      id: json['id'] as String,
      name: json['name'] as String,
      imageUrl: json['image_url'] as String?,
      prepTime: (json['prep_time'] as num?)?.toInt(),
      cookTime: (json['cook_time'] as num?)?.toInt(),
    );
  }
}

/// Summary of the Meal linked to a meal_event / recurrence_rule. Backend
/// populates it when `meal_id` is set; null on recipe-only and free-text
/// events. Old clients ignore the field cleanly — the backend additively
/// layered it onto the existing response shape.
class MealSummary {
  final String id;
  final String name;
  final int componentCount;
  final List<String> componentImageUrls;

  const MealSummary({
    required this.id,
    required this.name,
    required this.componentCount,
    this.componentImageUrls = const [],
  });

  factory MealSummary.fromJson(Map<String, dynamic> json) {
    final imgs = (json['component_image_urls'] as List? ?? [])
        .map((e) => e as String)
        .toList();
    return MealSummary(
      id: json['id'] as String,
      name: json['name'] as String,
      componentCount: (json['component_count'] as num?)?.toInt() ?? 0,
      componentImageUrls: imgs,
    );
  }
}

class MealEvent {
  final String id;
  final String title;
  final DateTime scheduledAt;
  final MealType mealType;
  final String status;
  final bool isShared;
  final RecipeSummary? recipe;

  /// Meal linkage — populated when the event was created in Meal mode.
  /// Mutually exclusive with [recipe] at the server (check constraint);
  /// both null means a free-text event.
  final String? mealId;
  final MealSummary? mealSummary;

  /// Null on older server responses (list endpoint used to omit it).
  final String? ownerId;

  /// Non-null when this event was materialized from a recurrence rule.
  final String? recurrenceRuleId;

  /// User's per-meal wall-clock reminder override, formatted "HH:MM".
  /// Null = user hasn't overridden → fall back to the slot default
  /// (matches backend `MEAL_SLOT_DEFAULT_TIMES`).
  final String? mealReminderTime;

  /// Effective reminder time, resolved server-side. Always populated —
  /// falls back to slot default when `mealReminderTime` is null. Safe
  /// to display verbatim on the detail screen.
  final String? reminderTime;

  const MealEvent({
    required this.id,
    required this.title,
    required this.scheduledAt,
    required this.mealType,
    required this.status,
    required this.isShared,
    this.recipe,
    this.mealId,
    this.mealSummary,
    this.ownerId,
    this.recurrenceRuleId,
    this.mealReminderTime,
    this.reminderTime,
  });

  factory MealEvent.fromJson(Map<String, dynamic> json) {
    return MealEvent(
      id: json['id'] as String,
      title: json['title'] as String,
      scheduledAt: DateTime.parse(json['scheduled_at'] as String).toLocal(),
      mealType: MealType.fromString(json['meal_type'] as String),
      status: json['status'] as String,
      isShared: json['is_shared'] as bool,
      recipe: json['recipe'] != null
          ? RecipeSummary.fromJson(json['recipe'] as Map<String, dynamic>)
          : null,
      mealId: json['meal_id'] as String?,
      mealSummary: json['meal_summary'] != null
          ? MealSummary.fromJson(
              json['meal_summary'] as Map<String, dynamic>,
            )
          : null,
      ownerId: json['owner_id'] as String?,
      recurrenceRuleId: json['recurrence_rule_id'] as String?,
      mealReminderTime: _parseTimeString(json['meal_reminder_time']),
      reminderTime: _parseTimeString(json['reminder_time']),
    );
  }

  /// Backend serializes `time` values as "HH:MM:SS" (Pydantic default).
  /// The UI just needs "HH:MM" — trim seconds if present so picker code
  /// downstream only deals with one shape.
  static String? _parseTimeString(dynamic raw) {
    if (raw == null) return null;
    final s = raw as String;
    if (s.length >= 5) return s.substring(0, 5);
    return s;
  }
}

/// Selected values from the Repeats picker. Null = non-recurring.
class RecurrenceValue {
  /// "weekly" | "biweekly" | "monthly"
  final String interval;

  /// Subset of {mon,tue,wed,thu,fri,sat,sun}. Exactly one weekday when
  /// [interval] is "monthly".
  final List<String> weekdays;

  /// Nullable end date (blank = forever).
  final DateTime? endDate;

  /// First/second/third/fourth/last — non-null only when interval=="monthly".
  final String? monthlyNth;

  const RecurrenceValue({
    required this.interval,
    required this.weekdays,
    this.endDate,
    this.monthlyNth,
  });

  RecurrenceValue copyWith({
    String? interval,
    List<String>? weekdays,
    DateTime? endDate,
    bool clearEndDate = false,
    String? monthlyNth,
    bool clearMonthlyNth = false,
  }) {
    return RecurrenceValue(
      interval: interval ?? this.interval,
      weekdays: weekdays ?? this.weekdays,
      endDate: clearEndDate ? null : (endDate ?? this.endDate),
      monthlyNth:
          clearMonthlyNth ? null : (monthlyNth ?? this.monthlyNth),
    );
  }
}

/// Full recurrence rule model — returned by GET/POST /recurrence-rules.
class RecurrenceRule {
  final String id;
  final String? title;
  final String? recipeId;

  /// Meal linkage — populated when the rule was created in Meal mode.
  /// Mutually exclusive with [recipeId] at the server.
  final String? mealId;
  final MealSummary? mealSummary;

  final String ownerId;
  final String mealType;
  final List<String> weekdays;
  final String interval;
  final String? monthlyNth;
  final DateTime startDate;
  final DateTime? endDate;
  final String tzName;
  final bool isShared;

  const RecurrenceRule({
    required this.id,
    required this.ownerId,
    required this.mealType,
    required this.weekdays,
    required this.interval,
    required this.startDate,
    required this.tzName,
    required this.isShared,
    this.title,
    this.recipeId,
    this.mealId,
    this.mealSummary,
    this.monthlyNth,
    this.endDate,
  });

  factory RecurrenceRule.fromJson(Map<String, dynamic> json) {
    return RecurrenceRule(
      id: json['id'] as String,
      title: json['title'] as String?,
      recipeId: json['recipe_id'] as String?,
      mealId: json['meal_id'] as String?,
      mealSummary: json['meal_summary'] != null
          ? MealSummary.fromJson(
              json['meal_summary'] as Map<String, dynamic>,
            )
          : null,
      ownerId: json['owner_id'] as String,
      mealType: json['meal_type'] as String,
      weekdays: (json['weekdays'] as List).cast<String>(),
      interval: json['interval'] as String,
      monthlyNth: json['monthly_nth'] as String?,
      startDate: DateTime.parse(json['start_date'] as String),
      endDate: json['end_date'] != null
          ? DateTime.parse(json['end_date'] as String)
          : null,
      tzName: json['tz_name'] as String,
      isShared: json['is_shared'] as bool,
    );
  }
}
