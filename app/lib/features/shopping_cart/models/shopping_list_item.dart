/// Shopping list item model.
class ShoppingListItem {
  final String id;
  final String name;
  final double? quantity;
  final String? unit;
  final bool isChecked;
  final DateTime? checkedAt;
  final String? category;
  final String? notes;
  final DateTime? dueAt;
  final String? dueReason;
  final String? mealEventId;
  final int priority;
  final String? addedByUserId;
  final String? addedByUserName;
  final String? assignedToUserId;
  final String? storeSection;
  final int? storeOrder;
  /// Set by the backend when a check-off auto-added this item to the pantry
  /// (pantry-3 hook). Null for every other update.
  final String? pantryIngredientId;
  final String? pantryId;

  ShoppingListItem({
    required this.id,
    required this.name,
    this.quantity,
    this.unit,
    this.isChecked = false,
    this.checkedAt,
    this.category,
    this.notes,
    this.dueAt,
    this.dueReason,
    this.mealEventId,
    this.priority = 0,
    this.addedByUserId,
    this.addedByUserName,
    this.assignedToUserId,
    this.storeSection,
    this.storeOrder,
    this.pantryIngredientId,
    this.pantryId,
  });

  factory ShoppingListItem.fromJson(Map<String, dynamic> json) {
    return ShoppingListItem(
      // id stays strict — a null id IS a real bug we want to see, not
      // render a ghost row.
      id: json['id'] as String,
      // Fall back to empty string rather than crash the whole list parse
      // if one row is missing a name. Rendering "" is better than a
      // caller-side exception that takes out the cart.
      name: (json['name'] as String?) ?? '',
      quantity: _tryParseQuantity(json['quantity']),
      unit: json['unit'] as String?,
      isChecked: json['is_checked'] as bool? ?? false,
      checkedAt: _tryParseDateTime(json['checked_at']),
      category: json['category'] as String?,
      notes: json['notes'] as String?,
      dueAt: _tryParseDateTime(json['due_at']),
      dueReason: json['due_reason'] as String?,
      mealEventId: json['meal_event_id'] as String?,
      priority: json['priority'] as int? ?? 0,
      addedByUserId: json['added_by_user_id'] as String?,
      addedByUserName: json['added_by_user_name'] as String?,
      assignedToUserId: json['assigned_to_user_id'] as String?,
      storeSection: json['store_section'] as String?,
      storeOrder: json['store_order'] as int?,
      pantryIngredientId: json['pantry_ingredient_id'] as String?,
      pantryId: json['pantry_id'] as String?,
    );
  }

  /// Parse a quantity without letting one bad row destroy the whole payload.
  ///
  /// This line used to be `(json['quantity'] as num?)?.toDouble()`, and that
  /// cast is why the cart was unusable from at least 2026-04 to 2026-09:
  /// Pydantic v2 renders a bare `Decimal` as a JSON **string**, the cast threw
  /// `_TypeError`, and because it threw inside `fromJson` it took down the
  /// **entire list parse** — not the one row. The user saw an empty cart, the
  /// server returned 200, and nothing was logged. **An empty cart and a broken
  /// cart look identical**, which is why it survived months.
  ///
  /// The server side is fixed (`schemas/json_types.py::JsonDecimal`) and, as
  /// of 2026-09-24, **no cart endpoint can emit a string quantity** — the ten
  /// paths that carry one either use `JsonDecimal` or call `float()`
  /// explicitly. So this is **defence in depth at a parse boundary, not a
  /// live bug fix**.
  ///
  /// It is still worth having, because the original defect arrived exactly
  /// this way: an endpoint built without the serializer. A new one added
  /// tomorrow would reintroduce it, and this guard turns "the cart is empty"
  /// back into "one quantity is missing".
  ///
  /// **A malformed quantity yields `null`, and the row still renders.** That
  /// is deliberate and matches this class's existing shape: `id` stays strict
  /// because a null id is a real bug worth seeing, `name` degrades to `''`
  /// rather than dropping the row. Quantity is not identity, so it degrades
  /// too. **Dropping the row would hide an item the user added** — worse than
  /// showing it without an amount, and harder to notice.
  static double? _tryParseQuantity(Object? raw) {
    if (raw == null) return null;
    if (raw is num) return raw.toDouble();
    // The Decimal-as-string case, and anything else stringy.
    if (raw is String) return double.tryParse(raw);
    // bool, List, Map, or anything else: no sane reading. Degrade, don't throw.
    return null;
  }

  static DateTime? _tryParseDateTime(Object? raw) {
    if (raw == null) return null;
    if (raw is! String) return null;
    return DateTime.tryParse(raw);
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      if (quantity != null) 'quantity': quantity,
      if (unit != null) 'unit': unit,
      'is_checked': isChecked,
      if (checkedAt != null) 'checked_at': checkedAt!.toIso8601String(),
      if (category != null) 'category': category,
      if (notes != null) 'notes': notes,
      if (dueAt != null) 'due_at': dueAt!.toIso8601String(),
      if (dueReason != null) 'due_reason': dueReason,
      if (mealEventId != null) 'meal_event_id': mealEventId,
      'priority': priority,
      if (addedByUserId != null) 'added_by_user_id': addedByUserId,
      if (assignedToUserId != null) 'assigned_to_user_id': assignedToUserId,
      if (storeSection != null) 'store_section': storeSection,
      if (storeOrder != null) 'store_order': storeOrder,
    };
  }

  ShoppingListItem copyWith({
    String? id,
    String? name,
    double? quantity,
    String? unit,
    bool? isChecked,
    DateTime? checkedAt,
    String? category,
    String? notes,
    DateTime? dueAt,
    String? dueReason,
    String? mealEventId,
    int? priority,
    String? addedByUserId,
    String? addedByUserName,
    String? assignedToUserId,
    String? storeSection,
    int? storeOrder,
  }) {
    return ShoppingListItem(
      id: id ?? this.id,
      name: name ?? this.name,
      quantity: quantity ?? this.quantity,
      unit: unit ?? this.unit,
      isChecked: isChecked ?? this.isChecked,
      checkedAt: checkedAt ?? this.checkedAt,
      category: category ?? this.category,
      notes: notes ?? this.notes,
      dueAt: dueAt ?? this.dueAt,
      dueReason: dueReason ?? this.dueReason,
      mealEventId: mealEventId ?? this.mealEventId,
      priority: priority ?? this.priority,
      addedByUserId: addedByUserId ?? this.addedByUserId,
      addedByUserName: addedByUserName ?? this.addedByUserName,
      assignedToUserId: assignedToUserId ?? this.assignedToUserId,
      storeSection: storeSection ?? this.storeSection,
      storeOrder: storeOrder ?? this.storeOrder,
    );
  }

  /// Get urgency level based on due date
  UrgencyLevel get urgencyLevel {
    if (dueAt == null) return UrgencyLevel.none;

    final now = DateTime.now();
    final hoursUntil = dueAt!.difference(now).inHours;

    if (hoursUntil < 0) return UrgencyLevel.overdue;
    if (hoursUntil < 2) return UrgencyLevel.urgent;
    if (hoursUntil < 24) return UrgencyLevel.today;
    if (hoursUntil < 72) return UrgencyLevel.soon;
    return UrgencyLevel.normal;
  }

  /// Format display text for quantity and unit
  String get quantityDisplay {
    if (quantity == null) return '';
    final q = quantity!;
    final qStr = q == q.truncate() ? q.truncate().toString() : q.toString();
    if (unit == null || unit!.isEmpty) return qStr;
    return '$qStr $unit';
  }
}

/// Urgency level for shopping list items
enum UrgencyLevel {
  overdue,
  urgent,
  today,
  soon,
  normal,
  none,
}

extension UrgencyLevelExtension on UrgencyLevel {
  String get displayName {
    switch (this) {
      case UrgencyLevel.overdue:
        return 'Overdue';
      case UrgencyLevel.urgent:
        return 'Urgent';
      case UrgencyLevel.today:
        return 'Today';
      case UrgencyLevel.soon:
        return 'Soon';
      case UrgencyLevel.normal:
        return 'Normal';
      case UrgencyLevel.none:
        return '';
    }
  }

  int get sortPriority {
    switch (this) {
      case UrgencyLevel.overdue:
        return 0;
      case UrgencyLevel.urgent:
        return 1;
      case UrgencyLevel.today:
        return 2;
      case UrgencyLevel.soon:
        return 3;
      case UrgencyLevel.normal:
        return 4;
      case UrgencyLevel.none:
        return 5;
    }
  }
}
