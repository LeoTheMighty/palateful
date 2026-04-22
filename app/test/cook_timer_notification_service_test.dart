// Tests for cook-timer notification Android actions parity (Story timer-1).
//
// The `flutter_local_notifications` plugin is wholly platform-channel
// based and cannot be initialized in a unit-test host. This test
// validates the shipped module-level `timerAndroidActions` list
// directly — the same list the service passes into
// `AndroidNotificationDetails.actions`.

import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/cook_timer_notification_service.dart';

void main() {
  group('timerAndroidActions', () {
    test('declares exactly four actions in the expected order', () {
      expect(timerAndroidActions, hasLength(4));
      expect(
        timerAndroidActions.map((a) => a.id).toList(),
        <String>[
          'TIMER_ADD_2_MIN',
          'TIMER_ADD_5_MIN',
          'TIMER_RESET',
          'TIMER_DISMISS',
        ],
      );
    });

    test('labels match the iOS DarwinNotificationAction category', () {
      expect(
        timerAndroidActions.map((a) => a.title).toList(),
        <String>['+ 2 min', '+ 5 min', 'Reset', 'Stop'],
      );
    });

    test('labels are short enough to fit in a notification banner', () {
      for (final action in timerAndroidActions) {
        expect(action.title.length, lessThanOrEqualTo(8),
            reason: 'Label "${action.title}" exceeds 8 chars — may truncate');
      }
    });

    test('all actions have showsUserInterface false', () {
      for (final action in timerAndroidActions) {
        expect(action.showsUserInterface, isFalse,
            reason:
                'Actions are handled in the background isolate, not foreground');
      }
    });

    test('cancelNotification defaults to true for every action', () {
      // The `AndroidNotificationAction` constructor default is true.
      // Re-assert so a future default change doesn't leave stale
      // banners hanging around after a tap.
      for (final action in timerAndroidActions) {
        expect(action.cancelNotification, isTrue);
      }
    });

    test('returns concrete AndroidNotificationAction instances', () {
      for (final action in timerAndroidActions) {
        expect(action, isA<AndroidNotificationAction>());
      }
    });
  });
}
