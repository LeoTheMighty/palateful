// Smoke tests for the LiveActivityService wiring (Story timer-2).
//
// The `live_activities` plugin is purely platform-channel backed and
// can't be initialized in a unit-test host. On any non-iOS platform
// (including the Dart test runner on macOS) `initialize()` no-ops via
// the `Platform.isIOS` guard and every subsequent call silently returns.
// This test verifies:
//   1. Uninitialized service gracefully no-ops (the app can call the
//      API before `initialize()` completes without crashing).
//   2. All four public methods are invokable without throwing.
//   3. The service doesn't leak state across tests.

import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/live_activity_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('LiveActivityService (no-op on non-iOS)', () {
    late LiveActivityService service;

    setUp(() {
      service = LiveActivityService();
    });

    test('startTimerActivity returns null before initialize', () async {
      final id = await service.startTimerActivity(
        notifId: 1,
        timerLabel: 'Rest dough',
        recipeName: 'Sourdough',
        duration: const Duration(minutes: 30),
      );
      expect(id, isNull);
    });

    test('updateTimerActivity does not throw when no activity exists',
        () async {
      await expectLater(
        service.updateTimerActivity(
          notifId: 42,
          newRemaining: const Duration(minutes: 5),
        ),
        completes,
      );
    });

    test('completeTimerActivity does not throw when no activity exists',
        () async {
      await expectLater(service.completeTimerActivity(42), completes);
    });

    test('endTimerActivity does not throw when no activity exists', () async {
      await expectLater(service.endTimerActivity(42), completes);
    });

    test('endAll does not throw when nothing is registered', () async {
      await expectLater(service.endAll(), completes);
    });

    test('initialize is idempotent and off-iOS is a graceful no-op',
        () async {
      await service.initialize();
      await service.initialize();
      // If we got here, the double-init path is safe.
      expect(true, isTrue);
    });
  });
}
