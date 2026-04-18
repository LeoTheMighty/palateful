import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/calendar/models/calendar_member.dart';

void main() {
  group('CalendarMember model edge cases', () {
    test('owner row has isOwner true and is not pending', () {
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
      expect(m.isPending, isFalse);
    });

    test('editor row carries invited_by_id', () {
      final m = CalendarMember.fromJson({
        'user_id': 'u-1',
        'name': 'Jane',
        'email': 'jane@example.com',
        'role': 'editor',
        'status': 'active',
        'invited_by_id': 'u-0',
        'created_at': '2026-04-17T10:00:00Z',
      });
      expect(m.invitedById, 'u-0');
      expect(m.isOwner, isFalse);
    });

    test('pending invitation has invitation_id and no user_id', () {
      final m = CalendarMember.fromJson({
        'user_id': null,
        'name': null,
        'email': 'bob@example.com',
        'role': 'editor',
        'status': 'pending',
        'invited_by_id': 'u-0',
        'created_at': '2026-04-17T10:00:00Z',
        'invitation_id': 'inv-42',
      });
      expect(m.isPending, isTrue);
      expect(m.userId, isNull);
      expect(m.invitationId, 'inv-42');
    });
  });
}
