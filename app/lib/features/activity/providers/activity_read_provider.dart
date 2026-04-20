import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import '../../../core/services/api_client.dart';
import '../../../core/services/error_reporter.dart';

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
  ActivityReadProvider(this._apiClient);

  final ApiClient _apiClient;

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
}
