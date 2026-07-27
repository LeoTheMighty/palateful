import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/pending_imports_reconciler.dart';

// ifh-4 — retry policy for the App Group reconciler.
//
// Every case here drives the reconciler through the same home_widget
// MethodChannel fake the base reconciler test uses, then reads back the
// persisted `share_pending_imports` array to assert on the retry state the
// reconciler wrote (attempt_count / next_attempt_at / failed / error_code).

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const channel = MethodChannel('home_widget');
  late Map<String, Object?> store;

  // Frozen clock so backoff deadlines are exact, not approximate.
  final now = DateTime.utc(2026, 7, 27, 12, 0, 0);

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

  void seed(List<Map<String, dynamic>> records) {
    store['share_pending_imports'] = jsonEncode(records);
  }

  List<Map<String, dynamic>> readBack() {
    final raw = store['share_pending_imports'] as String;
    return (jsonDecode(raw) as List)
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
  }

  Map<String, dynamic> record({
    String id = 'rec-1',
    int? attemptCount,
    String? nextAttemptAt,
    bool? failed,
  }) {
    return <String, dynamic>{
      'id': id,
      'book_id': 'book-1',
      'source_type': 'url',
      'url': 'https://example.com/r/$id',
      if (attemptCount != null) 'attempt_count': attemptCount,
      if (nextAttemptAt != null) 'next_attempt_at': nextAttemptAt,
      if (failed != null) 'failed': failed,
    };
  }

  DioException dioError({int? status, Object? body}) {
    final options = RequestOptions(path: '/v1/recipe-books/book-1/import');
    return DioException(
      requestOptions: options,
      response: status == null
          ? null
          : Response<Object?>(
              requestOptions: options,
              statusCode: status,
              data: body,
            ),
      type: status == null
          ? DioExceptionType.connectionError
          : DioExceptionType.badResponse,
    );
  }

  /// Builds a reconciler on the frozen clock whose POST always throws
  /// [error], recording how many POSTs were attempted.
  ({PendingImportsReconciler reconciler, List<String> posted}) failing(
    Object error,
  ) {
    final posted = <String>[];
    final reconciler = PendingImportsReconciler(
      (bookId, body) async {
        posted.add(body['idempotency_key'] as String);
        throw error;
      },
      now: () => now,
    );
    return (reconciler: reconciler, posted: posted);
  }

  group('transient failures', () {
    test('network exception increments attempt_count and sets next_attempt_at',
        () async {
      seed([record()]);
      final harness = failing(dioError());

      await harness.reconciler.reconcile();

      expect(harness.posted, ['rec-1']);
      final leftover = readBack();
      expect(leftover, hasLength(1));
      expect(leftover.first['attempt_count'], 1);
      expect(leftover.first['retryable'], true);
      expect(leftover.first['failed'], isNull);
      expect(
        DateTime.parse(leftover.first['next_attempt_at'] as String),
        now.add(const Duration(seconds: 1)),
      );
    });

    test('server retryable:true overrides a 4xx status', () async {
      seed([record()]);
      final harness = failing(
        dioError(status: 409, body: {'error_code': 4090, 'retryable': true}),
      );

      await harness.reconciler.reconcile();

      final leftover = readBack();
      expect(leftover.first['failed'], isNull);
      expect(leftover.first['attempt_count'], 1);
      expect(leftover.first['error_code'], 4090);
    });

    for (final status in [408, 409, 429, 500, 502, 503]) {
      test('status $status is transient under the fallback heuristic',
          () async {
        seed([record()]);
        final harness = failing(dioError(status: status, body: 'gateway down'));

        await harness.reconciler.reconcile();

        final leftover = readBack();
        expect(leftover.first['failed'], isNull, reason: 'status $status');
        expect(leftover.first['attempt_count'], 1, reason: 'status $status');
      });
    }

    test('backoff schedule matches the published curve', () async {
      expect(PendingImportsReconciler.backoffSchedule, const <Duration>[
        Duration(seconds: 1),
        Duration(seconds: 4),
        Duration(seconds: 16),
        Duration(minutes: 1),
        Duration(minutes: 5),
        Duration(minutes: 30),
      ]);

      // Drive attempts 1..5 and assert each persisted deadline lands on the
      // matching schedule entry.
      const expected = <int, Duration>{
        0: Duration(seconds: 1),
        1: Duration(seconds: 4),
        2: Duration(seconds: 16),
        3: Duration(minutes: 1),
        4: Duration(minutes: 5),
      };
      for (final entry in expected.entries) {
        seed([record(attemptCount: entry.key)]);
        final harness = failing(dioError(status: 503));

        await harness.reconciler.reconcile();

        final leftover = readBack();
        expect(leftover.first['attempt_count'], entry.key + 1);
        expect(
          DateTime.parse(leftover.first['next_attempt_at'] as String),
          now.add(entry.value),
          reason: 'attempt ${entry.key + 1}',
        );
      }
    });

    test('record is marked failed once attempts are exhausted', () async {
      seed([record(attemptCount: PendingImportsReconciler.maxAttempts - 1)]);
      final harness = failing(dioError(status: 503));

      await harness.reconciler.reconcile();

      final leftover = readBack();
      expect(leftover, hasLength(1));
      expect(leftover.first['attempt_count'], PendingImportsReconciler.maxAttempts);
      expect(leftover.first['failed'], true);
      expect(leftover.first['error_code'], 'retries_exhausted');
      expect(leftover.first.containsKey('next_attempt_at'), isFalse);
    });

    test('exhaustion keeps the server error_code when the body carried one',
        () async {
      seed([record(attemptCount: PendingImportsReconciler.maxAttempts - 1)]);
      final harness = failing(
        dioError(status: 500, body: {'error_code': 5000}),
      );

      await harness.reconciler.reconcile();

      expect(readBack().first['error_code'], 5000);
    });

    test('a failed record is never re-POSTed', () async {
      seed([record(failed: true)]);
      final harness = failing(dioError(status: 503));

      await harness.reconciler.reconcile();

      expect(harness.posted, isEmpty);
      expect(readBack(), hasLength(1));
    });
  });

  group('permanent failures', () {
    test('server retryable:false marks the record failed without a retry',
        () async {
      seed([record()]);
      final harness = failing(
        dioError(status: 400, body: {'error_code': 4000, 'retryable': false}),
      );

      await harness.reconciler.reconcile();

      expect(harness.posted, ['rec-1']);
      final leftover = readBack();
      expect(leftover, hasLength(1));
      expect(leftover.first['failed'], true);
      expect(leftover.first['retryable'], false);
      expect(leftover.first['error_code'], 4000);
      expect(leftover.first['attempt_count'], isNull);
      expect(leftover.first.containsKey('next_attempt_at'), isFalse);
    });

    test('retryable:false in a string-encoded body is still honored', () async {
      seed([record()]);
      final harness = failing(
        dioError(
          status: 415,
          body: jsonEncode({'error_code': 4150, 'retryable': false}),
        ),
      );

      await harness.reconciler.reconcile();

      final leftover = readBack();
      expect(leftover.first['failed'], true);
      expect(leftover.first['error_code'], 4150);
    });

    for (final status in [400, 403, 404, 413, 415, 422]) {
      test('status $status is permanent under the fallback heuristic',
          () async {
        seed([record()]);
        final harness = failing(dioError(status: status));

        await harness.reconciler.reconcile();

        final leftover = readBack();
        expect(leftover.first['failed'], true, reason: 'status $status');
        expect(leftover.first['retryable'], false, reason: 'status $status');
      });
    }

    test('a permanent failure does not re-POST on the next tick', () async {
      seed([record()]);
      var posts = 0;
      final reconciler = PendingImportsReconciler(
        (bookId, body) async {
          posts++;
          throw dioError(status: 400, body: {'retryable': false});
        },
        now: () => now,
      );

      await reconciler.reconcile();
      await reconciler.reconcile();

      expect(posts, 1);
    });
  });

  group('next_attempt_at gating', () {
    test('record is skipped while its backoff window is open', () async {
      final pending = record(
        attemptCount: 2,
        nextAttemptAt: now.add(const Duration(minutes: 5)).toIso8601String(),
      );
      seed([pending]);
      final harness = failing(dioError(status: 503));

      await harness.reconciler.reconcile();

      expect(harness.posted, isEmpty);
      final leftover = readBack();
      expect(leftover, hasLength(1));
      // Untouched — same attempt_count, same deadline.
      expect(leftover.first['attempt_count'], 2);
      expect(leftover.first['next_attempt_at'], pending['next_attempt_at']);
    });

    test('record is retried once the backoff window has elapsed', () async {
      seed([
        record(
          attemptCount: 2,
          nextAttemptAt: now.subtract(const Duration(seconds: 1)).toIso8601String(),
        ),
      ]);
      final harness = failing(dioError(status: 503));

      await harness.reconciler.reconcile();

      expect(harness.posted, ['rec-1']);
      expect(readBack().first['attempt_count'], 3);
    });

    test('an unparseable next_attempt_at does not strand the record',
        () async {
      seed([record(nextAttemptAt: 'not-a-timestamp')]);
      final harness = failing(dioError(status: 503));

      await harness.reconciler.reconcile();

      expect(harness.posted, ['rec-1']);
    });

    test('a gated record does not block its siblings', () async {
      seed([
        record(
          id: 'gated',
          nextAttemptAt: now.add(const Duration(minutes: 30)).toIso8601String(),
        ),
        record(id: 'due'),
      ]);
      final posted = <String>[];
      final reconciler = PendingImportsReconciler(
        (bookId, body) async => posted.add(body['idempotency_key'] as String),
        now: () => now,
      );

      await reconciler.reconcile();

      expect(posted, ['due']);
      expect(readBack().map((r) => r['id']), ['gated']);
    });
  });

  group('legacy records', () {
    test('a record with no retry fields is treated as retryable', () async {
      seed([
        {
          'id': 'legacy-1',
          'book_id': 'book-1',
          'source_type': 'pdf',
          's3_key': 'imports/2026/u/1.pdf',
        },
      ]);
      final harness = failing(dioError());

      await harness.reconciler.reconcile();

      expect(harness.posted, ['legacy-1']);
      final leftover = readBack();
      expect(leftover.first['attempt_count'], 1);
      expect(leftover.first['s3_key'], 'imports/2026/u/1.pdf');
    });

    test('a string attempt_count is parsed rather than reset', () async {
      seed([
        {
          'id': 'rec-1',
          'book_id': 'book-1',
          'source_type': 'url',
          'url': 'https://x',
          'attempt_count': '3',
        },
      ]);
      final harness = failing(dioError(status: 503));

      await harness.reconciler.reconcile();

      final leftover = readBack();
      expect(leftover.first['attempt_count'], 4);
      expect(
        DateTime.parse(leftover.first['next_attempt_at'] as String),
        now.add(const Duration(minutes: 1)),
      );
    });
  });

  test('a successful POST still drops the record', () async {
    seed([record(attemptCount: 3)]);
    final reconciler = PendingImportsReconciler(
      (bookId, body) async {},
      now: () => now,
    );

    await reconciler.reconcile();

    expect(readBack(), isEmpty);
  });
}
