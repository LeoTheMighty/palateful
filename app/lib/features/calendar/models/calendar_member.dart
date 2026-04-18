// CalendarMember model — mirrors the backend ListCalendarMembers response shape
// for both active members and pending invitations (discriminated by status).

class CalendarMember {
  final String? userId;
  final String? name;
  final String? email;
  final String role;
  final String status; // 'active' | 'pending'
  final String? invitedById;
  final String? invitationId; // present only when status == 'pending'
  final DateTime createdAt;

  const CalendarMember({
    required this.role,
    required this.status,
    required this.createdAt,
    this.userId,
    this.name,
    this.email,
    this.invitedById,
    this.invitationId,
  });

  factory CalendarMember.fromJson(Map<String, dynamic> json) {
    return CalendarMember(
      userId: json['user_id'] as String?,
      name: json['name'] as String?,
      email: json['email'] as String?,
      role: json['role'] as String,
      status: json['status'] as String,
      invitedById: json['invited_by_id'] as String?,
      invitationId: json['invitation_id'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }

  bool get isPending => status == 'pending';
  bool get isOwner => role == 'owner';
}
