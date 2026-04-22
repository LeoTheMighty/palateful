// rmc-4 — unit tests for the MealEventCoalescer helper.
//
// All timer behavior is exercised inside `FakeAsync.run` so CI never
// burns wall-clock time on debounce waits.

import 'package:fake_async/fake_async.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/state/meal_event_coalescer.dart';

void main() {
  group('MealEventCoalescer', () {
    test('52 schedules within 50ms → 0 invocations before window closes', () {
      FakeAsync().run((async) {
        final coalescer = MealEventCoalescer();
        var calls = 0;
        for (var i = 0; i < 52; i++) {
          coalescer.schedule(() => calls++);
          async.elapse(const Duration(milliseconds: 1));
        }
        // 52ms elapsed total. Debounce window is 100ms, so nothing fires.
        expect(calls, 0);
        // Elapse the remaining time — the window closes at the last
        // schedule + 100ms (schedule i=51 was at 51ms of fake time, window
        // fires at 151ms of fake time; we're at 52ms). Elapse 100ms more.
        async.elapse(const Duration(milliseconds: 100));
        expect(calls, 1,
            reason: 'Debounce must fire exactly once at window close');
      });
    });

    test('idle after window close — later schedule fires independently', () {
      FakeAsync().run((async) {
        final coalescer = MealEventCoalescer();
        var calls = 0;
        coalescer.schedule(() => calls++);
        async.elapse(const Duration(milliseconds: 150));
        expect(calls, 1);
        expect(coalescer.isScheduled, isFalse);

        // A later schedule starts a fresh window.
        coalescer.schedule(() => calls++);
        async.elapse(const Duration(milliseconds: 50));
        expect(calls, 1);
        async.elapse(const Duration(milliseconds: 50));
        expect(calls, 2);
      });
    });

    test('cold-stop: cancel() between schedule and fire → no invocation', () {
      FakeAsync().run((async) {
        final coalescer = MealEventCoalescer();
        var calls = 0;
        coalescer.schedule(() => calls++);
        async.elapse(const Duration(milliseconds: 50));
        coalescer.cancel();
        async.elapse(const Duration(milliseconds: 200));
        expect(calls, 0);
        expect(coalescer.isScheduled, isFalse);
      });
    });

    test('last-event-elision guard: 52nd schedule still fires', () {
      FakeAsync().run((async) {
        final coalescer = MealEventCoalescer();
        final callbacksFired = <int>[];
        // 52 schedules, 1ms apart, each closing over its index. The last
        // callback must be the one that fires — `schedule` replaces the
        // pending callback every time.
        for (var i = 0; i < 52; i++) {
          coalescer.schedule(() => callbacksFired.add(i));
          async.elapse(const Duration(milliseconds: 1));
        }
        async.elapse(const Duration(milliseconds: 150));
        expect(callbacksFired, [51],
            reason: 'Only the most-recent callback should run');
      });
    });

    test('schedule() after fire starts a fresh timer (re-arm)', () {
      FakeAsync().run((async) {
        final coalescer = MealEventCoalescer();
        var calls = 0;
        coalescer.schedule(() => calls++);
        async.elapse(const Duration(milliseconds: 100));
        expect(calls, 1);
        // Second burst.
        coalescer.schedule(() => calls++);
        coalescer.schedule(() => calls++);
        async.elapse(const Duration(milliseconds: 99));
        expect(calls, 1);
        async.elapse(const Duration(milliseconds: 1));
        expect(calls, 2);
      });
    });

    test('custom duration is honored', () {
      FakeAsync().run((async) {
        final coalescer = MealEventCoalescer(
          duration: const Duration(milliseconds: 500),
        );
        var calls = 0;
        coalescer.schedule(() => calls++);
        async.elapse(const Duration(milliseconds: 400));
        expect(calls, 0);
        async.elapse(const Duration(milliseconds: 100));
        expect(calls, 1);
      });
    });

    test('cancel on idle coalescer is a no-op', () {
      final coalescer = MealEventCoalescer();
      expect(() => coalescer.cancel(), returnsNormally);
      expect(() => coalescer.cancel(), returnsNormally);
    });
  });
}
