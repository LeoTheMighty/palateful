import 'dart:async';

import 'cook_session_persister.dart';

/// Coalesces a burst of [markDirty] calls into a single write after a
/// 250ms idle window. Cook-mode mutation handlers (step advance, toggle
/// ingredient, timer start/stop) can fire in rapid bursts; naive save
/// per mutation would blow past SharedPreferences' throughput budget.
///
/// Usage:
///
/// ```dart
/// final debouncer = CookSessionDebouncer(CookSessionPersister());
/// // ... mutation handler:
/// debouncer.markDirty(key, () => _snapshot());
/// // ... on AppLifecycleState.paused:
/// await debouncer.flushNow();
/// ```
class CookSessionDebouncer {
  static const Duration debounceWindow = Duration(milliseconds: 250);

  final CookSessionPersister _persister;
  Timer? _timer;
  String? _pendingKey;
  CookSessionState Function()? _pendingProducer;

  CookSessionDebouncer(this._persister);

  /// Schedule a write 250ms from now. Subsequent calls before the timer
  /// fires reset the window and replace the pending producer (so the
  /// eventual save reflects the latest state snapshot, not the first
  /// one queued).
  void markDirty(String key, CookSessionState Function() stateProducer) {
    _pendingKey = key;
    _pendingProducer = stateProducer;
    _timer?.cancel();
    _timer = Timer(debounceWindow, _flush);
  }

  /// Cancels any pending timer, invokes the latest producer, and awaits
  /// the save. Idempotent: no pending state = no-op, no throw. Call
  /// from `AppLifecycleState.paused` (primary trigger; `dispose` fires
  /// too late when the OS has already killed the process).
  Future<void> flushNow() async {
    _timer?.cancel();
    _timer = null;
    final key = _pendingKey;
    final producer = _pendingProducer;
    if (key == null || producer == null) return;
    _pendingKey = null;
    _pendingProducer = null;
    final state = producer();
    await _persister.save(key, state);
  }

  /// Cancel any pending write without flushing. Used after [clear]
  /// calls so a queued save can't resurrect state that was explicitly
  /// cleared (reset button, post-cook Done).
  void discardPending() {
    _timer?.cancel();
    _timer = null;
    _pendingKey = null;
    _pendingProducer = null;
  }

  void _flush() {
    _timer = null;
    final key = _pendingKey;
    final producer = _pendingProducer;
    if (key == null || producer == null) return;
    _pendingKey = null;
    _pendingProducer = null;
    final state = producer();
    // Fire and forget; internal save errors are absorbed by the
    // persister (warning log, preserve prior value). Returning Future
    // here would force the Timer callback into async space without any
    // caller able to await it.
    _persister.save(key, state);
  }
}
