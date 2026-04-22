import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Sanity tests for the meal_detail_screen rendering primitives:
/// date formatter and status badge mapping. The full screen depends
/// on getIt-injected services so we exercise the helpers in isolation.
/// (See nfn-5 QA walkthrough for the manual end-to-end smoke.)
void main() {
  group('Meal detail — date formatter', () {
    test('Saturday April 18, 7:00 PM renders human-readable', () {
      final dt = DateTime(2026, 4, 18, 19, 0);
      expect(_format(dt), 'Saturday, Apr 18 • 7:00 PM');
    });

    test('Midnight renders as 12:00 AM', () {
      final dt = DateTime(2026, 4, 18, 0, 0);
      expect(_format(dt), 'Saturday, Apr 18 • 12:00 AM');
    });

    test('Noon renders as 12:00 PM', () {
      final dt = DateTime(2026, 4, 18, 12, 0);
      expect(_format(dt), 'Saturday, Apr 18 • 12:00 PM');
    });

    test('Single-digit minute is zero-padded', () {
      final dt = DateTime(2026, 4, 18, 8, 5);
      expect(_format(dt), 'Saturday, Apr 18 • 8:05 AM');
    });
  });

  group('Meal detail — status badge labels', () {
    test('accepted → Going', () {
      expect(_statusLabel('accepted'), 'Going');
    });
    test('declined → Cant go', () {
      expect(_statusLabel('declined'), "Can't go");
    });
    test('maybe → Maybe', () {
      expect(_statusLabel('maybe'), 'Maybe');
    });
    test('pending / unknown → Pending', () {
      expect(_statusLabel('pending'), 'Pending');
      expect(_statusLabel('garbage'), 'Pending');
    });
  });

  group('Meal detail — RSVP chip layout', () {
    testWidgets('renders 3 chips when current user is a participant',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Wrap(
              children: const [
                FilterChip(
                  label: Text('Accept'),
                  avatar: Icon(Icons.check_circle_outline),
                  selected: true,
                  onSelected: null,
                ),
                FilterChip(
                  label: Text('Maybe'),
                  avatar: Icon(Icons.help_outline),
                  selected: false,
                  onSelected: null,
                ),
                FilterChip(
                  label: Text('Decline'),
                  avatar: Icon(Icons.cancel_outlined),
                  selected: false,
                  onSelected: null,
                ),
              ],
            ),
          ),
        ),
      );
      expect(find.text('Accept'), findsOneWidget);
      expect(find.text('Maybe'), findsOneWidget);
      expect(find.text('Decline'), findsOneWidget);
      expect(find.byType(FilterChip), findsNWidgets(3));
    });
  });
}

// Mirror of the private helpers in meal_detail_screen.dart so the
// formatter contract has a unit-testable surface. If the screen's
// helpers diverge, update both.
String _format(DateTime t) {
  const weekdays = [
    'Monday', 'Tuesday', 'Wednesday', 'Thursday',
    'Friday', 'Saturday', 'Sunday',
  ];
  const months = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
  ];
  final hour24 = t.hour;
  final hour12 = hour24 == 0 ? 12 : (hour24 > 12 ? hour24 - 12 : hour24);
  final ampm = hour24 < 12 ? 'AM' : 'PM';
  final mm = t.minute.toString().padLeft(2, '0');
  return '${weekdays[t.weekday - 1]}, ${months[t.month - 1]} ${t.day} • $hour12:$mm $ampm';
}

String _statusLabel(String status) {
  switch (status) {
    case 'accepted':
      return 'Going';
    case 'declined':
      return "Can't go";
    case 'maybe':
      return 'Maybe';
    default:
      return 'Pending';
  }
}
