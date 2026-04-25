import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/pending_imports_reconciler.dart';

// Reconciler tests. The reconciler reads a JSON array from the
// home_widget MethodChannel under key `share_pending_imports`, posts
// each to /v1/recipe-books/{bookId}/import, and writes back only
// the records whose POST failed retryably.

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const channel = MethodChannel('home_widget');
  late Map<String, Object?> store;

  setUp(() {
    debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
    store = {};
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
      switch (call.method) {
        case 'setAppGroupId':
          return null;
        case 'saveWidgetData':
          final args = (call.arguments as Map?)?.cast<String, Object?>() ?? {};
          final id = args['id'] as String?;
          if (id != null) store[id] = args['data'];
          return true;
        case 'getWidgetData':
          final args = (call.arguments as Map?)?.cast<String, Object?>() ?? {};
          final id = args['id'] as String?;
          return id == null ? null : store[id];
      }
      return null;
    });
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null);
    debugDefaultTargetPlatformOverride = null;
  });

  test('reconcile posts each pending record and clears the list on success', () async {
    store['share_pending_imports'] = jsonEncode([
      {
        'id': 'uuid-1',
        'book_id': 'book-1',
        'source_type': 'url',
        'url': 'https://allrecipes.com/r/1',
      },
      {
        'id': 'uuid-2',
        'book_id': 'book-1',
        'source_type': 'pdf',
        's3_key': 'imports/2026/u/1.pdf',
        'etag': 'etagvalue',
        'mime_type': 'application/pdf',
      },
    ]);

    final calls = <_Call>[];
    final reconciler = PendingImportsReconciler((bookId, body) async {
      calls.add(_Call(bookId: bookId, body: body));
    });
    await reconciler.reconcile();

    expect(calls.length, 2);
    expect(calls[0].bookId, 'book-1');
    expect(calls[0].body['source_type'], 'url');
    expect(calls[0].body['idempotency_key'], 'uuid-1');
    expect(calls[1].body['s3_key'], 'imports/2026/u/1.pdf');
    expect(calls[1].body['etag'], 'etagvalue');
    final leftover = jsonDecode(store['share_pending_imports'] as String) as List;
    expect(leftover, isEmpty);
  });

  test('reconcile leaves retryable failures in the list for next tick', () async {
    store['share_pending_imports'] = jsonEncode([
      {
        'id': 'ok-1',
        'book_id': 'book-1',
        'source_type': 'url',
        'url': 'https://x',
      },
      {
        'id': 'fail-1',
        'book_id': 'book-1',
        'source_type': 'url',
        'url': 'https://y',
      },
    ]);

    final reconciler = PendingImportsReconciler((bookId, body) async {
      if (body['idempotency_key'] == 'fail-1') {
        throw StateError('502');
      }
    });
    await reconciler.reconcile();

    final leftover = jsonDecode(store['share_pending_imports'] as String) as List;
    expect(leftover.length, 1);
    expect((leftover.first as Map)['id'], 'fail-1');
  });
}

class _Call {
  final String bookId;
  final Map<String, dynamic> body;
  _Call({required this.bookId, required this.body});
}
