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

  const RecipeSummary({
    required this.id,
    required this.name,
    this.imageUrl,
  });

  factory RecipeSummary.fromJson(Map<String, dynamic> json) {
    return RecipeSummary(
      id: json['id'] as String,
      name: json['name'] as String,
      imageUrl: json['image_url'] as String?,
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
  final String ownerId;

  const MealEvent({
    required this.id,
    required this.title,
    required this.scheduledAt,
    required this.mealType,
    required this.status,
    required this.isShared,
    this.recipe,
    required this.ownerId,
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
      ownerId: json['owner_id'] as String,
    );
  }
}
