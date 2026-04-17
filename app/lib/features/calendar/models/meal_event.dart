/// Meal event models for the calendar feature.

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

class MealEvent {
  final String id;
  final String title;
  final DateTime scheduledAt;
  final MealType mealType;
  final String status;
  final bool isShared;
  final RecipeSummary? recipe;

  /// Null on older server responses (list endpoint used to omit it).
  final String? ownerId;

  /// Non-null when this event was materialized from a recurrence rule.
  final String? recurrenceRuleId;

  const MealEvent({
    required this.id,
    required this.title,
    required this.scheduledAt,
    required this.mealType,
    required this.status,
    required this.isShared,
    this.recipe,
    this.ownerId,
    this.recurrenceRuleId,
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
      ownerId: json['owner_id'] as String?,
      recurrenceRuleId: json['recurrence_rule_id'] as String?,
    );
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
    this.monthlyNth,
    this.endDate,
  });

  factory RecurrenceRule.fromJson(Map<String, dynamic> json) {
    return RecurrenceRule(
      id: json['id'] as String,
      title: json['title'] as String?,
      recipeId: json['recipe_id'] as String?,
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
