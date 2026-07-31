import 'dart:convert';
import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:home_widget/home_widget.dart';

import 'api_client.dart';
import 'error_reporter.dart';

typedef ImportPoster = Future<void> Function(
  String bookId,
  Map<String, dynamic> body,
);

/// Reads the `share_pending_imports` App Group key — written by
/// PalatefulShare when the user taps Save — and resubmits any records the
/// extension couldn't close out itself. Backstop for:
///   (a) extension killed mid-flight before its URLSession delegate could
///       clear the record, and
///   (b) file-share path where a background PUT may still be running when
///       the extension process ends.
///
/// Records are POSTed to `/v1/recipe-books/{book}/import` with the exact
/// payload the Swift side built (including `idempotency_key`). Server
/// dedupes by that key so a double-fire is harmless.
///
/// ifh-4 retry policy — a POST ends in exactly one of three states:
///   * **success** → record is dropped from the App Group list.
///   * **transient failure** (network blip, `retryable: true` from the
///     server, or the 5xx/429/408/409 status heuristic when the server is
///     too old to send the field) → `attempt_count` is incremented and
///     `next_attempt_at` is pushed out along [backoffSchedule]. The record
///     survives and is skipped by later ticks until that timestamp passes.
///     Once [maxAttempts] failures have accumulated the record flips to
///     `failed: true` — exhausted retries are permanent, so a share is
///     never silently dropped.
///   * **permanent failure** (`retryable: false`, or any other 4xx under
///     the heuristic) → `failed: true` plus the server's `error_code`, with
///     no further POSTs. ifh-5's FailedImportsService consumes those rows.
class PendingImportsReconciler {
  /// Delay applied *after* the Nth consecutive transient failure, matching
  /// the schedule published in the import-flow-hardening epic.
  ///
  /// With [maxAttempts] at 6 the last delay actually applied is the 5m
  /// entry (the 6th failure flips the record to `failed`); the 30m tail is
  /// kept so raising the cap doesn't silently change the published curve.
  static const List<Duration> backoffSchedule = <Duration>[
    Duration(seconds: 1),
    Duration(seconds: 4),
    Duration(seconds: 16),
    Duration(minutes: 1),
    Duration(minutes: 5),
    Duration(minutes: 30),
  ];

  /// Transient failures allowed before the record is treated as permanently
  /// failed. Bounded by design — no infinite background retry loops.
  static const int maxAttempts = 6;

  final ImportPoster _post;
  final DateTime Function() _now;

  PendingImportsReconciler(this._post, {DateTime Function()? now})
      : _now = now ?? DateTime.now;

  /// Convenience constructor that delegates to `ApiClient.postImportForBook`.
  factory PendingImportsReconciler.forApi(
    ApiClient api, {
    DateTime Function()? now,
  }) {
    return PendingImportsReconciler(
      (bookId, body) => api.postImportForBook(bookId, body).then((_) {}),
      now: now,
    );
  }

  Future<void> reconcile() async {
    // iOS-only: App Group reads route through home_widget which has no
    // Android/web implementation. Skip silently rather than 500-spam
    // error_logs with MissingPluginException.
    if (kIsWeb || defaultTargetPlatform != TargetPlatform.iOS) return;
    try {
      final raw = await HomeWidget.getWidgetData<String>('share_pending_imports');
      if (raw == null || raw.isEmpty || raw == '[]') return;

      final list = (jsonDecode(raw) as List<dynamic>)
          .whereType<Map>()
          .map((m) => Map<String, dynamic>.from(m))
          .toList();
      if (list.isEmpty) return;

      final now = _now().toUtc();
      final survivors = <Map<String, dynamic>>[];
      for (final record in list) {
        final bookId = record['book_id'] as String?;
        if (bookId == null || bookId.isEmpty) continue;

        // Terminal state — ifh-5's UI owns these (retry resets the counters
        // and clears the flag). Never re-POST behind the user's back.
        if (record['failed'] == true) {
          survivors.add(record);
          continue;
        }

        // Backoff hasn't elapsed — leave the record exactly as written.
        final nextAttemptAt = _parseTimestamp(record['next_attempt_at']);
        if (nextAttemptAt != null && nextAttemptAt.isAfter(now)) {
          survivors.add(record);
          continue;
        }

        try {
          final body = <String, dynamic>{
            'source_type': record['source_type'],
            'idempotency_key': record['id'],
            if (record['url'] != null) 'url': record['url'],
            if (record['s3_key'] != null) 's3_key': record['s3_key'],
            if (record['etag'] != null) 'etag': record['etag'],
            if (record['filename'] != null) 'filename': record['filename'],
            if (record['mime_type'] != null) 'mime_type': record['mime_type'],
          };
          await _post(bookId, body);
        } catch (e, st) {
          survivors.add(_applyFailure(record, e, now));
          ErrorReporter.report(
            e,
            st,
            area: 'share_extension',
            operation: 'reconcile_import',
          );
        }
      }

      await HomeWidget.saveWidgetData<String>(
        'share_pending_imports',
        jsonEncode(survivors),
      );
    } catch (e, st) {
      ErrorReporter.report(e, st, area: 'share_extension', operation: 'reconcile_read');
      debugPrint('PendingImportsReconciler error: $e');
    }
  }

  /// Returns the record as it should be persisted after a failed POST.
  /// Never mutates [record] in place — the caller's list stays the
  /// pre-attempt snapshot.
  Map<String, dynamic> _applyFailure(
    Map<String, dynamic> record,
    Object error,
    DateTime now,
  ) {
    final classification = _classify(error);
    final updated = Map<String, dynamic>.from(record);
    updated['retryable'] = classification.retryable;
    if (classification.errorCode != null) {
      updated['error_code'] = classification.errorCode;
    }

    if (!classification.retryable) {
      updated['failed'] = true;
      updated.remove('next_attempt_at');
      return updated;
    }

    final attempts = _attemptCount(record['attempt_count']) + 1;
    updated['attempt_count'] = attempts;
    if (attempts >= maxAttempts) {
      updated['failed'] = true;
      updated['error_code'] ??= 'retries_exhausted';
      updated.remove('next_attempt_at');
      return updated;
    }

    final delay =
        backoffSchedule[min(attempts - 1, backoffSchedule.length - 1)];
    updated['next_attempt_at'] = now.add(delay).toIso8601String();
    return updated;
  }

  /// Permanent-vs-transient is a server contract (ifh-1 ships `retryable`
  /// in the failure envelope); the status heuristic is only the fallback
  /// for older servers and for bodyless network failures.
  _Classification _classify(Object error) {
    if (error is DioException) {
      final response = error.response;
      if (response != null) {
        final body = _asMap(response.data);
        final retryable = body?['retryable'];
        final errorCode = body?['error_code'];
        return _Classification(
          retryable is bool ? retryable : _retryableForStatus(response.statusCode),
          errorCode,
        );
      }
    }
    // Network exception, plugin error, or any non-HTTP throw — assume the
    // cause is transient and let the attempt cap bound it.
    return const _Classification(true, null);
  }

  bool _retryableForStatus(int? status) {
    if (status == null || status >= 500) return true;
    if (status == 408 || status == 409 || status == 429) return true;
    return status < 400;
  }

  Map<String, dynamic>? _asMap(Object? data) {
    if (data is Map) return Map<String, dynamic>.from(data);
    if (data is String && data.isNotEmpty) {
      try {
        final decoded = jsonDecode(data);
        if (decoded is Map) return Map<String, dynamic>.from(decoded);
      } catch (_) {
        // Non-JSON error body (HTML gateway page, plain text) — fall through
        // to the status-code heuristic.
      }
    }
    return null;
  }

  int _attemptCount(Object? raw) {
    if (raw is int) return raw < 0 ? 0 : raw;
    if (raw is num) return raw < 0 ? 0 : raw.toInt();
    if (raw is String) {
      final parsed = int.tryParse(raw);
      if (parsed != null) return parsed < 0 ? 0 : parsed;
    }
    return 0;
  }

  /// Legacy records (written before this story) carry no `next_attempt_at`,
  /// and a garbled one shouldn't strand a share forever — both cases fall
  /// through to "eligible now".
  DateTime? _parseTimestamp(Object? raw) {
    if (raw is! String || raw.isEmpty) return null;
    return DateTime.tryParse(raw)?.toUtc();
  }
}

class _Classification {
  final bool retryable;
  final Object? errorCode;

  const _Classification(this.retryable, this.errorCode);
}
