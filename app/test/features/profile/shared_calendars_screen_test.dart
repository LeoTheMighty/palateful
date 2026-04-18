import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/calendar/models/calendar.dart';

void main() {
  // Pure model filter assertion — exercises the predicate the
  // SharedCalendarsScreen uses to derive the editor-only list.
  group('Shared-calendars filter', () {
    final now = DateTime(2026, 4, 18);
    Calendar make({required String id, required String role}) => Calendar(
          id: id,
          name: 'Meal Prep $id',
          ownerId: 'owner-x',
          userRole: role,
          memberCount: 2,
          createdAt: now,
          updatedAt: now,
        );

    test('filters out owner calendars and keeps editor calendars', () {
      final all = [
        make(id: '1', role: 'owner'),
        make(id: '2', role: 'editor'),
        make(id: '3', role: 'editor'),
      ];
      final shared = all.where((c) => !c.isOwner).toList();
      expect(shared.length, 2);
      expect(shared.every((c) => c.userRole == 'editor'), isTrue);
    });

    test('returns empty when caller owns every calendar', () {
      final all = [
        make(id: '1', role: 'owner'),
        make(id: '2', role: 'owner'),
      ];
      expect(all.where((c) => !c.isOwner).toList(), isEmpty);
    });
  });
}
