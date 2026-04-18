// Meal model — mirrors backend MealResponse (mcv-2) + MealSummaryResponse
// (mcv-2's grid list shape).
//
// Two data classes:
//   * Meal — full detail with hydrated components, for /meals/{id}.
//   * MealSummary — grid-tile shape, for /meals + /recipe-books/*/meals.

class Meal {
  final String id;
  final String name;
  final String? description;
  final String recipeBookId;
  final DateTime? archivedAt;
  final DateTime createdAt;
  final DateTime updatedAt;
  final List<MealComponent> components;
  final bool isFavorite;

  const Meal({
    required this.id,
    required this.name,
    required this.recipeBookId,
    required this.createdAt,
    required this.updatedAt,
    this.description,
    this.archivedAt,
    this.components = const [],
    this.isFavorite = false,
  });

  bool get isArchived => archivedAt != null;
  int get componentCount => components.length;
  int get availableComponentCount =>
      components.where((c) => c.available).length;

  factory Meal.fromJson(Map<String, dynamic> json) {
    final rawComponents = (json['components'] as List? ?? [])
        .cast<Map<String, dynamic>>();
    return Meal(
      id: json['id'] as String,
      name: json['name'] as String,
      description: json['description'] as String?,
      recipeBookId: json['recipe_book_id'] as String,
      archivedAt: _parseNullableDate(json['archived_at']),
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
      components: rawComponents.map(MealComponent.fromJson).toList(),
      isFavorite: json['is_favorite'] as bool? ?? false,
    );
  }

  Meal copyWith({
    String? name,
    String? description,
    DateTime? archivedAt,
    List<MealComponent>? components,
    bool? isFavorite,
    bool clearArchivedAt = false,
  }) {
    return Meal(
      id: id,
      name: name ?? this.name,
      description: description ?? this.description,
      recipeBookId: recipeBookId,
      archivedAt: clearArchivedAt ? null : (archivedAt ?? this.archivedAt),
      createdAt: createdAt,
      updatedAt: updatedAt,
      components: components ?? this.components,
      isFavorite: isFavorite ?? this.isFavorite,
    );
  }
}

class MealComponent {
  final String recipeId;
  final String name;
  final String? imageUrl;
  final int? prepTime;
  final int? cookTime;
  final String? bookName;
  final int orderIndex;
  final bool available;
  final String? lastKnownName;

  const MealComponent({
    required this.recipeId,
    required this.name,
    required this.orderIndex,
    this.imageUrl,
    this.prepTime,
    this.cookTime,
    this.bookName,
    this.available = true,
    this.lastKnownName,
  });

  String get displayName =>
      available ? name : (lastKnownName ?? name);

  factory MealComponent.fromJson(Map<String, dynamic> json) {
    return MealComponent(
      recipeId: json['recipe_id'] as String,
      name: json['name'] as String? ?? '',
      imageUrl: json['image_url'] as String?,
      prepTime: (json['prep_time'] as num?)?.toInt(),
      cookTime: (json['cook_time'] as num?)?.toInt(),
      bookName: json['book_name'] as String?,
      orderIndex: (json['order_index'] as num?)?.toInt() ?? 0,
      available: json['available'] as bool? ?? true,
      lastKnownName: json['last_known_name'] as String?,
    );
  }
}

/// Thin grid-tile shape for list endpoints.
class MealSummary {
  final String id;
  final String name;
  final String? description;
  final String recipeBookId;
  final int componentCount;
  final List<String> componentImageUrls;
  final DateTime? archivedAt;
  final DateTime updatedAt;

  const MealSummary({
    required this.id,
    required this.name,
    required this.recipeBookId,
    required this.componentCount,
    required this.updatedAt,
    this.description,
    this.componentImageUrls = const [],
    this.archivedAt,
  });

  bool get isArchived => archivedAt != null;

  factory MealSummary.fromJson(Map<String, dynamic> json) {
    final imgs = (json['component_image_urls'] as List? ?? [])
        .map((e) => e as String)
        .toList();
    return MealSummary(
      id: json['id'] as String,
      name: json['name'] as String,
      description: json['description'] as String?,
      recipeBookId: json['recipe_book_id'] as String,
      componentCount: (json['component_count'] as num?)?.toInt() ?? 0,
      componentImageUrls: imgs,
      archivedAt: _parseNullableDate(json['archived_at']),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }
}

DateTime? _parseNullableDate(dynamic raw) {
  if (raw == null) return null;
  return DateTime.parse(raw as String);
}
