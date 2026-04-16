import 'pantry_ingredient.dart';

/// The user's default pantry plus its non-archived ingredients.
class Pantry {
  final String id;
  final String name;
  final String role; // owner | editor | viewer
  final List<PantryIngredient> items;

  const Pantry({
    required this.id,
    required this.name,
    required this.role,
    required this.items,
  });

  factory Pantry.fromJson(Map<String, dynamic> json) {
    final rawItems = (json['items'] as List<dynamic>?) ?? const [];
    return Pantry(
      id: json['id'] as String,
      name: json['name'] as String? ?? 'My Pantry',
      role: json['role'] as String? ?? 'viewer',
      items: rawItems
          .map((e) => PantryIngredient.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  Pantry copyWith({List<PantryIngredient>? items}) => Pantry(
        id: id,
        name: name,
        role: role,
        items: items ?? this.items,
      );
}
