import 'dart:convert';

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
/// dedupes by that key so a double-fire is harmless. Successful records
/// drop from the list; retryable failures survive for the next tick.
class PendingImportsReconciler {
  final ImportPoster _post;

  PendingImportsReconciler(this._post);

  /// Convenience constructor that delegates to `ApiClient.postImportForBook`.
  factory PendingImportsReconciler.forApi(ApiClient api) {
    return PendingImportsReconciler(
      (bookId, body) => api.postImportForBook(bookId, body).then((_) {}),
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

      final survivors = <Map<String, dynamic>>[];
      for (final record in list) {
        final bookId = record['book_id'] as String?;
        if (bookId == null || bookId.isEmpty) continue;

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
          survivors.add(record);
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
}
