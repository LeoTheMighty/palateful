import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'mutation_event.dart';

export 'mutation_event.dart';

/// App-wide broadcast bus for [MutationEvent]s.
///
/// Why non-autoDispose + module-level singleton (epic Locked Decision #5):
/// `StreamProvider.autoDispose` would tear down the underlying subscription
/// the moment the last widget unmounted, dropping any event that arrived in
/// the microtask gap before a new subscriber mounted. A `Provider<Stream>`
/// wrapping a long-lived singleton `StreamController.broadcast()` keeps the
/// stream hot for the whole app lifetime.
///
/// See `README.md` in this directory for emit/subscribe conventions.

// Module-level singleton. Intentionally never closed — it lives for the
// process lifetime. Closing it would silently drop events on hot-restart
// and make every subscriber `onDone` fire.
// `sync: true` → subscribers that listen via `ref.listen(mutationBusProvider,
// ...)` are invoked before `emitMutation(...)` returns, which makes widget
// tests deterministic without `pumpAndSettle` timeouts.
// ignore: close_sinks
final StreamController<MutationEvent> _controller =
    StreamController<MutationEvent>.broadcast(sync: true);

/// Riverpod wrapper. **NOT `autoDispose`** — see epic Locked Decision #5.
///
/// Subscribe via:
///
/// ```dart
/// ref.listen<Stream<MutationEvent>>(mutationBusProvider, (_, stream) {
///   // called once, with the stream — listen inline for per-event callbacks
/// });
/// ```
///
/// For per-event reactions, subscribers usually use
/// `ref.listen(mutationBusProvider.select(...))` *inside* a provider body
/// and call `ref.invalidateSelf()`. See `README.md` for the full recipe.
final Provider<Stream<MutationEvent>> mutationBusProvider =
    Provider<Stream<MutationEvent>>((ref) => _controller.stream);

/// Emit a mutation event for everyone on the bus.
///
/// Prefer calling this from **inside a `*Service` method on the success
/// branch of the API call** (epic Locked Decision #1). UI handlers should
/// only emit when there is no service layer yet (e.g. `ImportHistoryScreen`
/// in rf-5), and those cases are flagged as cleanup debt in the epic.
void emitMutation(MutationEvent event) {
  // Defensive — should never happen; the controller is never closed.
  if (_controller.isClosed) return;
  _controller.add(event);
}

/// Non-Riverpod stream handle on the bus, for getIt services and other
/// contexts without a `Ref`. Equivalent to `ref.read(mutationBusProvider)`.
Stream<MutationEvent> mutationBusStream() => _controller.stream;

/// Test-only: does the bus have any active subscriber? Used by
/// `mutation_bus_test.dart` to assert the singleton does not leak
/// subscribers across subscribe/dispose cycles.
@visibleForTesting
bool mutationBusHasListener() => _controller.hasListener;
