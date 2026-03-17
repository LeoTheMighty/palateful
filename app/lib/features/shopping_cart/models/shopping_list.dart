import 'shopping_list_item.dart';

/// Shopping list model.
class ShoppingList {
  final String id;
  final String name;
  final String status;
  final String ownerId;
  final bool isShared;
  final String? shareCode;
  final String? widgetColor;
  final String sortBy;
  final List<ShoppingListItem> items;
  final List<ShoppingListMember> members;
  final DateTime createdAt;
  final DateTime updatedAt;

  ShoppingList({
    required this.id,
    required this.name,
    this.status = 'active',
    required this.ownerId,
    this.isShared = false,
    this.shareCode,
    this.widgetColor,
    this.sortBy = 'category',
    this.items = const [],
    this.members = const [],
    required this.createdAt,
    required this.updatedAt,
  });

  factory ShoppingList.fromJson(Map<String, dynamic> json) {
    return ShoppingList(
      id: json['id'] as String,
      name: json['name'] as String,
      status: json['status'] as String? ?? 'active',
      ownerId: json['owner_id'] as String,
      isShared: json['is_shared'] as bool? ?? false,
      shareCode: json['share_code'] as String?,
      widgetColor: json['widget_color'] as String?,
      sortBy: json['sort_by'] as String? ?? 'category',
      items: (json['items'] as List<dynamic>?)
              ?.map((i) => ShoppingListItem.fromJson(i as Map<String, dynamic>))
              .toList() ??
          [],
      members: (json['members'] as List<dynamic>?)
              ?.map(
                  (m) => ShoppingListMember.fromJson(m as Map<String, dynamic>))
              .toList() ??
          [],
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }

  ShoppingList copyWith({
    String? id,
    String? name,
    String? status,
    String? ownerId,
    bool? isShared,
    String? shareCode,
    String? widgetColor,
    String? sortBy,
    List<ShoppingListItem>? items,
    List<ShoppingListMember>? members,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return ShoppingList(
      id: id ?? this.id,
      name: name ?? this.name,
      status: status ?? this.status,
      ownerId: ownerId ?? this.ownerId,
      isShared: isShared ?? this.isShared,
      shareCode: shareCode ?? this.shareCode,
      widgetColor: widgetColor ?? this.widgetColor,
      sortBy: sortBy ?? this.sortBy,
      items: items ?? this.items,
      members: members ?? this.members,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  /// Get count of unchecked items
  int get uncheckedCount => items.where((i) => !i.isChecked).length;

  /// Get count of checked items
  int get checkedCount => items.where((i) => i.isChecked).length;

  /// Get items grouped by urgency
  Map<UrgencyLevel, List<ShoppingListItem>> get itemsByUrgency {
    final result = <UrgencyLevel, List<ShoppingListItem>>{};
    for (final level in UrgencyLevel.values) {
      result[level] = [];
    }
    for (final item in items.where((i) => !i.isChecked)) {
      result[item.urgencyLevel]!.add(item);
    }
    return result;
  }

  /// Check if there are urgent items
  bool get hasUrgentItems {
    return items.any((i) =>
        !i.isChecked &&
        (i.urgencyLevel == UrgencyLevel.urgent ||
            i.urgencyLevel == UrgencyLevel.overdue));
  }
}

/// Shopping list member model.
class ShoppingListMember {
  final String id;
  final String userId;
  final String? userName;
  final String? userEmail;
  final String role;
  final bool notifyOnAdd;
  final bool notifyOnCheck;
  final bool notifyOnDeadline;
  final DateTime? lastSeenAt;
  final DateTime? archivedAt;
  final DateTime joinedAt;

  ShoppingListMember({
    required this.id,
    required this.userId,
    this.userName,
    this.userEmail,
    this.role = 'editor',
    this.notifyOnAdd = true,
    this.notifyOnCheck = false,
    this.notifyOnDeadline = true,
    this.lastSeenAt,
    this.archivedAt,
    required this.joinedAt,
  });

  factory ShoppingListMember.fromJson(Map<String, dynamic> json) {
    return ShoppingListMember(
      id: json['id'] as String? ?? json['user_id'] as String,
      userId: json['user_id'] as String,
      userName: json['user_name'] as String?,
      userEmail: json['user_email'] as String?,
      role: json['role'] as String? ?? 'editor',
      notifyOnAdd: json['notify_on_add'] as bool? ?? true,
      notifyOnCheck: json['notify_on_check'] as bool? ?? false,
      notifyOnDeadline: json['notify_on_deadline'] as bool? ?? true,
      lastSeenAt: json['last_seen_at'] != null
          ? DateTime.parse(json['last_seen_at'] as String)
          : null,
      archivedAt: json['archived_at'] != null
          ? DateTime.parse(json['archived_at'] as String)
          : null,
      joinedAt: DateTime.parse(json['joined_at'] as String),
    );
  }

  bool get isOnline {
    if (lastSeenAt == null) return false;
    return DateTime.now().difference(lastSeenAt!).inMinutes < 5;
  }
}

/// Online user presence info.
class OnlineUser {
  final String id;
  final String? name;
  final String status;
  final DateTime timestamp;

  OnlineUser({
    required this.id,
    this.name,
    this.status = 'online',
    required this.timestamp,
  });

  factory OnlineUser.fromJson(Map<String, dynamic> json) {
    return OnlineUser(
      id: json['user_id'] as String,
      name: json['user_name'] as String?,
      status: json['status'] as String? ?? 'online',
      timestamp: DateTime.parse(json['timestamp'] as String),
    );
  }

  bool get isShopping => status == 'shopping';
  bool get isOnline => status == 'online' || status == 'shopping';
}
