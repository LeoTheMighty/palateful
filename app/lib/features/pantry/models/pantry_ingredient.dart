/// A single row in the user's pantry, as returned by
/// `GET /v1/pantries/default`.
class PantryIngredient {
  final String pantryId;
  final String ingredientId;
  final String? ingredientName;
  final String? category;
  final double quantityDisplay;
  final String unitDisplay;
  final double quantityNormalized;
  final String unitNormalized;
  final String? storageLocation; // fridge | pantry | freezer | null
  final DateTime? expiresAt;
  final DateTime createdAt;
  final DateTime updatedAt;
  final DateTime? archivedAt;

  const PantryIngredient({
    required this.pantryId,
    required this.ingredientId,
    required this.quantityDisplay,
    required this.unitDisplay,
    required this.quantityNormalized,
    required this.unitNormalized,
    required this.createdAt,
    required this.updatedAt,
    this.ingredientName,
    this.category,
    this.storageLocation,
    this.expiresAt,
    this.archivedAt,
  });

  factory PantryIngredient.fromJson(Map<String, dynamic> json) {
    return PantryIngredient(
      pantryId: json['pantry_id'] as String,
      ingredientId: json['ingredient_id'] as String,
      ingredientName: json['ingredient_name'] as String?,
      category: json['category'] as String?,
      quantityDisplay: _asDouble(json['quantity_display']),
      unitDisplay: (json['unit_display'] as String?) ?? '',
      quantityNormalized: _asDouble(json['quantity_normalized']),
      unitNormalized: (json['unit_normalized'] as String?) ?? '',
      storageLocation: json['storage_location'] as String?,
      expiresAt: _asDateTime(json['expires_at']),
      createdAt: _asDateTime(json['created_at']) ?? DateTime.now(),
      updatedAt: _asDateTime(json['updated_at']) ?? DateTime.now(),
      archivedAt: _asDateTime(json['archived_at']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'pantry_id': pantryId,
      'ingredient_id': ingredientId,
      'quantity_display': quantityDisplay,
      'unit_display': unitDisplay,
      'quantity_normalized': quantityNormalized,
      'unit_normalized': unitNormalized,
      if (storageLocation != null) 'storage_location': storageLocation,
      if (expiresAt != null) 'expires_at': expiresAt!.toIso8601String(),
    };
  }

  /// Days between "now" and `expiresAt`. Negative if expired. Null if no
  /// expiry set. Rounded down — "in 6 hours" reads as "0 days."
  int? daysUntilExpiry({DateTime? now}) {
    if (expiresAt == null) return null;
    final reference = now ?? DateTime.now();
    final diff = expiresAt!.difference(reference);
    return diff.inDays;
  }
}

double _asDouble(dynamic v) {
  if (v == null) return 0.0;
  if (v is num) return v.toDouble();
  if (v is String) return double.tryParse(v) ?? 0.0;
  return 0.0;
}

DateTime? _asDateTime(dynamic v) {
  if (v == null) return null;
  if (v is DateTime) return v;
  if (v is String) return DateTime.tryParse(v);
  return null;
}
