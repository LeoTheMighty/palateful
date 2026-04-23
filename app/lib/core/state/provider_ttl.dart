import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/error_reporter.dart';

/// ffm-6 — TTL-keepalive helper for long-lived providers.
///
/// Calls `ref.keepAlive()` once, then schedules a periodic timer
/// that invokes [revalidate] every [maxAge]. Timer is cancelled when
/// the provider disposes, so there's no leak across hot-reload or
/// container swaps.
///
/// Intended for reference-data providers whose value is "mostly
/// stable" session-wide but whose source of truth may change
/// out-of-band — another device mutating the row, auth refresh,
/// cold resume after the app was backgrounded for an hour. The
/// MutationBus handles in-app mutations; TTL is the backstop.
///
/// Conventional usage inside a FutureProvider body:
///
/// ```dart
/// final recipeBooksProvider =
///     FutureProvider.autoDispose<List<RecipeBook>>((ref) async {
///   keepAliveWithTtl(
///     ref,
///     maxAge: const Duration(minutes: 10),
///     revalidate: () async => ref.invalidateSelf(),
///   );
///   // ... MutationBus subscription, initial fetch, etc.
/// });
/// ```
///
/// Silent-revalidation contract:
/// - The previous value is preserved across the revalidate via
///   Riverpod's `AsyncValue.copyWithPrevious`. UI consumers using
///   `when(skipLoadingOnRefresh: true)` (or reading `.value`
///   directly) see the cached data throughout the refresh — no
///   `AsyncLoading` flip, no spinner.
/// - On fetch failure, the rebuilt provider exposes an
///   `AsyncError.copyWithPrevious` — the previous data is still
///   accessible. The TTL helper additionally reports the failure to
///   [ErrorReporter] with `area: 'provider_ttl'` so silent failures
///   surface in Crashlytics / the audit dashboard.
/// - Only one TTL timer is registered per provider body; each
///   rebuild creates a new timer and cancels the previous one via
///   `ref.onDispose`.
void keepAliveWithTtl(
  Ref ref, {
  required Duration maxAge,
  required Future<void> Function() revalidate,
}) {
  assert(
    maxAge > Duration.zero,
    'keepAliveWithTtl: maxAge must be positive',
  );
  ref.keepAlive();

  // Guard against a Timer callback being dispatched after the
  // provider's rebuild — Riverpod will have fired `onDispose` and
  // cancelled the timer, but the Dart scheduler may still drain a
  // pending callback on the current microtask. `_disposed` is a
  // cheap fast-exit.
  var disposed = false;
  final timer = Timer.periodic(maxAge, (_) async {
    if (disposed) return;
    try {
      await revalidate();
    } catch (e, st) {
      // Keep stale data visible; surface the failure through the
      // error pipeline instead of flipping the UI to an error state.
      ErrorReporter.report(
        e,
        st,
        area: 'provider_ttl',
        operation: 'revalidate',
      );
    }
  });
  ref.onDispose(() {
    disposed = true;
    timer.cancel();
  });
}
