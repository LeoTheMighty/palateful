import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/activity/providers/activity_tab_provider.dart';

void main() {
  group('initialTabFromCounts (abi-4)', () {
    test('imports > notifications → Imports', () {
      expect(
        initialTabFromCounts(notifications: 1, importsActionable: 3),
        ActivityTab.imports,
      );
    });

    test('notifications > imports → Notifications', () {
      expect(
        initialTabFromCounts(notifications: 3, importsActionable: 1),
        ActivityTab.notifications,
      );
    });

    test('tie → Notifications (cold-start default)', () {
      expect(
        initialTabFromCounts(notifications: 2, importsActionable: 2),
        ActivityTab.notifications,
      );
    });

    test('zero-zero → Notifications (cold-start default)', () {
      expect(
        initialTabFromCounts(notifications: 0, importsActionable: 0),
        ActivityTab.notifications,
      );
    });

    test('only imports present → Imports', () {
      expect(
        initialTabFromCounts(notifications: 0, importsActionable: 5),
        ActivityTab.imports,
      );
    });

    test('only notifications present → Notifications', () {
      expect(
        initialTabFromCounts(notifications: 5, importsActionable: 0),
        ActivityTab.notifications,
      );
    });
  });

  group('ActivityTab.fromWire', () {
    test('imports wire', () {
      expect(ActivityTab.fromWire('imports'), ActivityTab.imports);
    });

    test('notifications wire', () {
      expect(
        ActivityTab.fromWire('notifications'),
        ActivityTab.notifications,
      );
    });

    test('unknown → Notifications (safe default)', () {
      expect(ActivityTab.fromWire('foo'), ActivityTab.notifications);
      expect(ActivityTab.fromWire(null), ActivityTab.notifications);
    });
  });
}
