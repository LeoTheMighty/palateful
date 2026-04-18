import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/calendar/models/calendar_member.dart';

void main() {
  group('CalendarMember.fromJson', () {
    test('parses an active member row', () {
      final m = CalendarMember.fromJson({
        'user_id': 'u-1',
        'name': 'Jane',
        'email': 'jane@example.com',
        'role': 'editor',
        'status': 'active',
        'invited_by_id': 'u-0',
        'created_at': '2026-04-17T10:00:00Z',
      });
      expect(m.role, 'editor');
      expect(m.status, 'active');
      expect(m.isPending, isFalse);
      expect(m.isOwner, isFalse);
      expect(m.email, 'jane@example.com');
    });

    test('parses an active owner row', () {
      final m = CalendarMember.fromJson({
        'user_id': 'u-0',
        'name': 'Leo',
        'email': 'leo@example.com',
        'role': 'owner',
        'status': 'active',
        'invited_by_id': null,
        'created_at': '2026-04-17T10:00:00Z',
      });
      expect(m.isOwner, isTrue);
      expect(m.invitedById, isNull);
    });

    test('parses a pending invitation row (email-only, no user yet)', () {
      final m = CalendarMember.fromJson({
        'user_id': null,
        'name': null,
        'email': 'newperson@example.com',
        'role': 'editor',
        'status': 'pending',
        'invited_by_id': 'u-0',
        'created_at': '2026-04-17T10:00:00Z',
        'invitation_id': 'inv-1',
      });
      expect(m.isPending, isTrue);
      expect(m.userId, isNull);
      expect(m.invitationId, 'inv-1');
      expect(m.email, 'newperson@example.com');
    });
  });
}
