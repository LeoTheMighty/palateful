import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import '../../../core/services/api_client.dart';
import '../../../core/services/error_reporter.dart';
import '../../../core/state/mutation_bus.dart';

/// Shared read-state + unread-count cache for the Activity Hub.
///
/// Responsibilities:
/// 1. Mark a batch of loaded activity IDs read with per-ID retry — on surface
///    open we fire once and tolerate transient failures so the UI stays
///    optimistic and the server eventually converges.
/// 2. Cache the unread count as a [ValueListenable] so the bottom-nav badge
///    can react to writes from other surfaces (ActivityScreen, ImportHistory)
///    without waiting on the 30s poll.
/// 3. abi-3: parse the new structured unread-count payload
///    (`{notifications, imports_actionable, count}`) into separate
///    `notificationsCount` + `importsActionableCount` fields. The existing
///    `unreadCount` is kept as the derived sum so downstream readers that
///    still use it don't break. When the server returns the legacy
///    `{count}` shape, `structuredCountsAvailable` flips false and per-tab
///    badges are expected to hide (bell still renders).
class ActivityReadProvider {
  ActivityReadProvider(this._apiClient) {
    // rf-5: subscribe to import events so the bell badge refreshes
    // eagerly without waiting on the 30s poll. The poll still runs
    // to cover cold-start + WS-missed states (epic AC #4 — double
    // path is intentional).
    _busSub = mutationBusStream().listen((event) {
      if (event is ImportItemDismissed ||
          event is ImportJobDismissed ||
          event is ImportItemRetried) {
        // ffm-3: record the timestamp BEFORE firing so a tick racing
        // immediately after sees the bus-driven reload as the
        // authoritative source within the dedup window.
        _lastMutationReloadAt = _nowMs();
        refreshUnreadCount();
      }
    });
  }

  final ApiClient _apiClient;
  StreamSubscription<MutationEvent>? _busSub;

  /// ffm-3 — wall-clock (ms since epoch) of the last bus-driven
  /// `refreshUnreadCount()` call. `0` means "never fired this session".
  /// Reads go through [_nowMs] so tests can swap in a fake clock.
  int _lastMutationReloadAt = 0;

  /// ffm-3 — window within which a scheduled tick will short-circuit
  /// its own unread-count refresh because the bus already produced
  /// fresh truth. Tuned to comfortably cover one round-trip; a 5s value
  /// leaves a flicker window on slow networks.
  static const Duration _mutationReloadFloor = Duration(seconds: 10);

  /// ffm-3 — injectable clock. Production reads `DateTime.now()`; tests
  /// swap in a monotonic fake via [debugSetClock] to avoid wall-clock
  /// flakes on CI.
  int Function() _clock = _defaultClock;
  static int _defaultClock() => DateTime.now().millisecondsSinceEpoch;
  int _nowMs() => _clock();

  /// Visible-for-testing clock override. Pass `null` to restore the
  /// real clock.
  @visibleForTesting
  void debugSetClock(int Function()? clock) {
    _clock = clock ?? _defaultClock;
  }

  /// Visible-for-testing hook so tests can inspect the dedup state
  /// directly rather than through wall-clock timing.
  @visibleForTesting
  int get lastMutationReloadAt => _lastMutationReloadAt;

  /// Visible-for-testing hook so tests can drive the ffm-3 fake-clock
  /// matrix without running the real MutationBus. Mirrors what the bus
  /// subscription does in production.
  @visibleForTesting
  void debugSetLastMutationReloadAt(int tsMs) {
    _lastMutationReloadAt = tsMs;
  }

  /// Release the MutationBus subscription. Tests call this in tearDown;
  /// production getIt lifecycle never calls it (the service lives for
  /// the process lifetime).
  void dispose() {
    _busSub?.cancel();
    _busSub = null;
    stopPolling();
  }

  /// Combined count (notifications + imports_actionable). Kept for
  /// backwards-compat — callers that only care about "is there anything
  /// in the bell" keep reading this.
  final ValueNotifier<int> unreadCount = ValueNotifier<int>(0);

  /// abi-3: Notifications-tab count from the structured payload. `0` when
  /// the server payload is the legacy `{count}` shape.
  final ValueNotifier<int> notificationsCount = ValueNotifier<int>(0);

  /// abi-3: Imports-tab actionable count from the structured payload. `0`
  /// when the server payload is the legacy `{count}` shape.
  final ValueNotifier<int> importsActionableCount = ValueNotifier<int>(0);

  /// abi-3: true iff the last server response included both `notifications`
  /// and `imports_actionable` keys. Per-tab badges gate their rendering on
  /// this so they don't attribute-misstate the split under an old-client /
  /// rolled-back server. The bell renders regardless.
  final ValueNotifier<bool> structuredCountsAvailable =
      ValueNotifier<bool>(false);

  /// One-time debug warning per session on old-client fallback.
  bool _warnedOldPayloadShape = false;

  /// Activity types whose rows live in the user_activity table but surface
  /// inside the Import Activity screen. Kept in sync with
  /// `_importActivityTypes` in `activity_screen.dart`.
  static const Set<String> importActivityTypes = {
    'import_started',
    'import_complete',
    'import_needs_review',
    'import_extracting',
    'import_item_complete',
    'import_failed',
  };

  /// Mark a set of loaded activity IDs read. Fires one PUT per id in
  /// parallel, with up to two retries per id on failure (200ms then 400ms
  /// exponential backoff). Individual failures are swallowed + reported to
  /// Crashlytics — the optimistic local flag has already updated the UI.
  Future<void> markIdsRead(Iterable<String> ids) async {
    final list = ids.toList(growable: false);
    if (list.isEmpty) return;
    await Future.wait(list.map(_markOneWithRetry));
  }

  Future<void> _markOneWithRetry(String id) async {
    const maxAttempts = 3;
    var backoff = const Duration(milliseconds: 200);
    for (var attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        await _apiClient.markActivityRead(id);
        return;
      } catch (e, st) {
        // Client-side 4xx (e.g. activity archived between fetch and mark)
        // is terminal — retrying won't make the row reappear. Drop the
        // write silently; the row is no longer contributing to unread.
        if (e is DioException) {
          final status = e.response?.statusCode ?? 0;
          if (status >= 400 && status < 500) return;
        }
        if (attempt == maxAttempts) {
          ErrorReporter.report(
            e,
            st,
            area: 'activity',
            operation: 'markActivityRead',
            extras: {'activity_id': id, 'attempts': attempt},
          );
          return;
        }
        await Future.delayed(backoff);
        backoff *= 2;
      }
    }
  }

  /// Mark every currently-unread import-typed activity read. Used by the
  /// Import Activity screen so opening that surface clears the badge
  /// contribution from import notifications. Non-import activities are
  /// left untouched.
  Future<void> markLoadedImportActivitiesRead() async {
    try {
      final response = await _apiClient.getActivities(limit: 100);
      final items = List<dynamic>.from(response.data['items'] ?? []);
      final ids = <String>[];
      for (final item in items) {
        final type = item['type']?.toString();
        final read = item['read'] == true;
        final id = item['id']?.toString();
        if (id != null && !read && type != null && importActivityTypes.contains(type)) {
          ids.add(id);
        }
      }
      await markIdsRead(ids);
      await refreshUnreadCount();
    } catch (e, st) {
      ErrorReporter.report(
        e,
        st,
        area: 'activity',
        operation: 'markLoadedImportActivitiesRead',
      );
    }
  }

  /// Re-fetch the server-authoritative unread count and broadcast it to
  /// listeners (e.g. the bottom-nav badge). Server wins on reconciliation.
  ///
  /// abi-3: parses the new structured payload if present, falling back
  /// to the legacy `{count}` shape.
  Future<void> refreshUnreadCount() async {
    try {
      final response = await _apiClient.getUnreadActivityCount();
      final data = response.data;
      final hasNotifications = data is Map && data.containsKey('notifications');
      final hasImportsActionable =
          data is Map && data.containsKey('imports_actionable');
      final structured = hasNotifications && hasImportsActionable;

      if (structured) {
        final n = (data['notifications'] as num?)?.toInt() ?? 0;
        final i = (data['imports_actionable'] as num?)?.toInt() ?? 0;
        if (notificationsCount.value != n) notificationsCount.value = n;
        if (importsActionableCount.value != i) importsActionableCount.value = i;
        if (!structuredCountsAvailable.value) {
          structuredCountsAvailable.value = true;
        }
        final sum = n + i;
        if (unreadCount.value != sum) unreadCount.value = sum;
      } else {
        // Legacy fallback — only `{count}`.
        final count = (data is Map ? data['count'] as num? : null)?.toInt() ?? 0;
        if (unreadCount.value != count) unreadCount.value = count;
        if (structuredCountsAvailable.value) {
          structuredCountsAvailable.value = false;
        }
        // Explicitly zero the per-tab counts so a stale value from a
        // previous structured response doesn't leak under the old-client
        // fallback (per-tab badges also hide via structuredCountsAvailable).
        if (notificationsCount.value != 0) notificationsCount.value = 0;
        if (importsActionableCount.value != 0) importsActionableCount.value = 0;
        if (!_warnedOldPayloadShape) {
          _warnedOldPayloadShape = true;
          debugPrint(
            'badge: old payload shape detected, per-tab badges suppressed',
          );
        }
      }
    } catch (_) {
      // Silent — we'll reconverge on the next poll.
    }
  }

  /// Overwrite the cached count without a network round-trip. Used when
  /// a caller already knows the new value (e.g. after mark-all-read).
  void setUnreadCount(int count) {
    if (unreadCount.value != count) {
      unreadCount.value = count;
    }
  }

  // ───────────────────────────────────────────────────────────────────
  // pfc-1: single-source 30s poll. Shell owns start/stop; tabs register
  // tick listeners. When a listener declares `contributesUnreadCount`,
  // the provider skips its own `/unread-count` fetch on each tick — the
  // consumer's richer fetch (e.g. notifications_tab's `/v1/activities`)
  // carries fresh truth via its own downstream `refreshUnreadCount()`.
  // ───────────────────────────────────────────────────────────────────

  static const Duration _pollInterval = Duration(seconds: 30);
  Timer? _pollTimer;
  final List<_TickListenerEntry> _tickListeners = [];
  int _activitiesFetchSubscribers = 0;

  /// True iff the provider currently owns a live `Timer.periodic`.
  @visibleForTesting
  bool get hasActiveTimer => _pollTimer?.isActive == true;

  @visibleForTesting
  int get tickListenerCount => _tickListeners.length;

  @visibleForTesting
  int get activitiesFetchSubscriberCount => _activitiesFetchSubscribers;

  /// Start the single app-wide 30s poll. Idempotent — second call is a
  /// no-op. Fires one immediate tick for cold-start reconciliation.
  void startPolling() {
    if (_pollTimer?.isActive == true) return;
    // Cold-start reconciliation: fire a tick right away so the badge
    // matches server truth without waiting 30s.
    _tick();
    _pollTimer = Timer.periodic(_pollInterval, (_) => _tick());
  }

  /// Stop the poll. Shell calls this on dispose.
  void stopPolling() {
    _pollTimer?.cancel();
    _pollTimer = null;
  }

  /// Register a per-tick refresh callback. Returns a disposer that the
  /// caller MUST invoke on dispose. Double-invoke of the disposer is
  /// guarded — subsequent calls are no-ops.
  ///
  /// When [contributesUnreadCount] is true, the provider suppresses its
  /// own `refreshUnreadCount()` on each tick while this listener is
  /// alive — the consumer's own fetch is expected to update
  /// `unreadCount` downstream. Use for consumers that fetch
  /// `/v1/activities` (which inherently carries the count). Do NOT set
  /// for consumers whose fetch does not carry the count (e.g. imports
  /// tab's `/v1/import-jobs`).
  VoidCallback registerTickListener(
    VoidCallback callback, {
    bool contributesUnreadCount = false,
  }) {
    final entry = _TickListenerEntry(callback, contributesUnreadCount);
    _tickListeners.add(entry);
    if (contributesUnreadCount) _activitiesFetchSubscribers++;

    var disposed = false;
    return () {
      if (disposed) return;
      disposed = true;
      _tickListeners.remove(entry);
      if (contributesUnreadCount) _activitiesFetchSubscribers--;
    };
  }

  /// Visible-for-testing hook so unit tests can drive the decision
  /// matrix without waiting 30s. Production callers go through the
  /// Timer.
  @visibleForTesting
  Future<void> debugTick() => _tick();

  Future<void> _tick() async {
    // Sentinel log for the manual walkthrough — DevTools console prints
    // this every 30s when the poll is alive. Stripped in release builds.
    debugPrint('[activity-read] tick');
    // Fire tab refreshes first. Copy the list so a disposer invoked
    // during callback dispatch doesn't mutate the iterator.
    for (final entry in List<_TickListenerEntry>.from(_tickListeners)) {
      try {
        entry.callback();
      } catch (e, st) {
        ErrorReporter.report(
          e,
          st,
          area: 'activity',
          operation: 'activity_read_tick_listener',
        );
      }
    }
    if (_activitiesFetchSubscribers == 0) {
      // ffm-3: if a MutationBus event just drove a `refreshUnreadCount`
      // within the dedup window, skip the tick's duplicate fetch. The
      // tab-listener callbacks above still ran — only the bell-count
      // round-trip is coalesced.
      if (_isWithinMutationReloadWindow()) {
        debugPrint(
          '[activity-read] tick suppressed: bus-driven reload within '
          '${_mutationReloadFloor.inSeconds}s',
        );
        return;
      }
      await refreshUnreadCount();
    }
  }

  bool _isWithinMutationReloadWindow() {
    if (_lastMutationReloadAt == 0) return false;
    return (_nowMs() - _lastMutationReloadAt) < _mutationReloadFloor.inMilliseconds;
  }
}

class _TickListenerEntry {
  _TickListenerEntry(this.callback, this.contributesUnreadCount);
  final VoidCallback callback;
  final bool contributesUnreadCount;
}
