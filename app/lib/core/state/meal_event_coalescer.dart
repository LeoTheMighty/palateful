import 'dart:async';

/// 100ms subscriber-side debounce wrapper (rmc-4).
///
/// Wraps a single `Timer`. `schedule(fn)` resets the timer to 100ms (or
/// the duration passed at construction). When the timer fires, the most
/// recently-scheduled callback runs exactly once.
///
/// Used by `mealEventsByRangeProvider` / `mealEventsByDayProvider` /
/// `upcomingEventsForMealProvider` to coalesce recurrence-materialization
/// storms (52 `MealEventCreated` in 50ms → one refetch) without
/// introducing a third-party debounce package.
///
/// Lifecycle:
/// - `schedule(fn)` — set/reset the timer to fire after [duration].
/// - `cancel()` — tear down any pending timer. Safe to call on an idle
///   coalescer.
/// - Use `ref.onDispose(coalescer.cancel)` in provider bodies so the
///   timer is cleaned up when the subscription tears down.
///
/// `schedule` overwrites the pending callback — the last caller wins.
/// That matches the refetch semantics we want: whichever invalidation
/// lands last during the debounce window is the one that actually runs.
class MealEventCoalescer {
  MealEventCoalescer({
    this.duration = const Duration(milliseconds: 100),
  });

  final Duration duration;
  Timer? _timer;

  /// Test-only: is a callback currently queued?
  bool get isScheduled => _timer?.isActive ?? false;

  /// Schedule [callback] to run after [duration] of quiet time. Resets
  /// the timer if one was already pending.
  void schedule(void Function() callback) {
    _timer?.cancel();
    _timer = Timer(duration, () {
      _timer = null;
      callback();
    });
  }

  /// Cancel any pending callback. Safe to call multiple times.
  void cancel() {
    _timer?.cancel();
    _timer = null;
  }
}
