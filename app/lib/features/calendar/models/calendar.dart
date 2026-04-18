// Calendar model — mirrors backend CalendarResponse.

class Calendar {
  final String id;
  final String name;
  final String? description;
  final bool isDefault;
  final bool isShared;
  final String ownerId;
  final String userRole;
  final int memberCount;
  final DateTime createdAt;
  final DateTime updatedAt;

  const Calendar({
    required this.id,
    required this.name,
    required this.ownerId,
    required this.userRole,
    required this.memberCount,
    required this.createdAt,
    required this.updatedAt,
    this.description,
    this.isDefault = false,
    this.isShared = false,
  });

  factory Calendar.fromJson(Map<String, dynamic> json) {
    return Calendar(
      id: json['id'] as String,
      name: json['name'] as String,
      description: json['description'] as String?,
      isDefault: json['is_default'] as bool? ?? false,
      isShared: json['is_shared'] as bool? ?? false,
      ownerId: json['owner_id'] as String,
      userRole: json['user_role'] as String,
      memberCount: (json['member_count'] as num?)?.toInt() ?? 1,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }

  bool get isOwner => userRole == 'owner';
}
