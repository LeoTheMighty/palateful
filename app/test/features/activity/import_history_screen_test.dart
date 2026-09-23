import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/activity/import_history_screen.dart';
import 'package:palateful/features/activity/providers/activity_read_provider.dart';
import 'package:palateful/features/recipes/add_recipe/batch_parser_service.dart';

/// Base instant for every fixture timestamp in this file.
///
/// `ImportHistoryScreen` routes a job's `created_at` through
/// `_contextualTime` → `_formatTime` (import_history_screen.dart:341,
/// :325) and renders the result on every history row (:872, :954).
/// That formatter is `DateTime.now()`-relative, so the rendered label
/// drifts as a frozen literal ages. The failed bucket itself has no
/// age cutoff — the fuse here is the label, not the filter.
/// The base sits 90 minutes back, not 2 hours: every `_formatTime` in
/// play buckets by whole hours, and a base exactly on the 1h/2h boundary
/// made `_at(0)` render '2h ago' while `_at(5)` rendered '1h ago'. At 90
/// minutes every offset used here stays inside one bucket with ~20
/// minutes of headroom, so two fixtures "five minutes apart" also read
/// the same. Nothing asserts these labels today; this keeps the first
/// test that does from being flaky by construction.
final DateTime _fixtureBase =
    DateTime.now().toUtc().subtract(const Duration(minutes: 90));

/// A fixture timestamp `minutesAfterBase` past [_fixtureBase]. The
/// three fixtures below all shared one literal, so they all share
/// offset 0 — same instant, same relative ordering as before.
String _at(int minutesAfterBase) =>
    _fixtureBase.add(Duration(minutes: minutesAfterBase)).toIso8601String();

Response<dynamic> _fakeResponse(dynamic data) {
  return Response(
    data: data,
    requestOptions: RequestOptions(path: ''),
    statusCode: 200,
  );
}

class _FakeApiClient extends ApiClient {
  List<Map<String, dynamic>> failedJobs;
  List<Map<String, dynamic>> failedItems;
  int dismissAllCount = 0;
  int dismissAllCalls = 0;

  _FakeApiClient({
    this.failedJobs = const [],
    this.failedItems = const [],
  });

  @override
  Future<Response> listImportJobs({
    String? status,
    int limit = 20,
    int offset = 0,
    bool includeArchived = false,
    bool archivedOnly = false,
    String? cursor,
  }) async {
    if (status == 'failed') {
      return _fakeResponse({'jobs': failedJobs});
    }
    return _fakeResponse({'jobs': []});
  }

  @override
  Future<Response> getImportItemsSeeAllCount() async =>
      _fakeResponse(
          {'archived': 0, 'read_and_old_completed': 0, 'total': 0});

  @override
  Future<Response> listImportItems(
    String jobId, {
    String? status,
    bool includeArchived = false,
  }) async {
    return _fakeResponse({'items': failedItems});
  }

  @override
  Future<Response> listImportItemsBatch(
    List<String> jobIds, {
    String? status,
    bool includeArchived = false,
  }) async {
    final out = <dynamic>[];
    for (final jobId in jobIds) {
      for (final item in failedItems) {
        out.add({...item, 'job_id': jobId});
      }
    }
    return _fakeResponse({'items': out});
  }

  @override
  Future<Response> dismissAllFailedImports() async {
    dismissAllCalls++;
    return _fakeResponse({'dismissed_count': dismissAllCount});
  }

  @override
  Future<Response> dismissImportItem(String itemId) async =>
      _fakeResponse({'item_id': itemId, 'job_dismissed': false});

  @override
  Future<Response> markActivityRead(String id) async =>
      _fakeResponse({'success': true});

  @override
  Future<Response> getActivities({int limit = 50, int offset = 0}) async =>
      _fakeResponse({'items': [], 'total': 0});

  @override
  Future<Response> getUnreadActivityCount() async =>
      _fakeResponse({'count': 0});
}

void _registerFakes(_FakeApiClient client) {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  gi.registerSingleton<ApiClient>(client);
  if (gi.isRegistered<BatchParserService>()) {
    gi.unregister<BatchParserService>();
  }
  gi.registerLazySingleton<BatchParserService>(() => BatchParserService());
  if (gi.isRegistered<ActivityReadProvider>()) {
    gi.unregister<ActivityReadProvider>();
  }
  gi.registerLazySingleton<ActivityReadProvider>(
    () => ActivityReadProvider(gi<ApiClient>()),
  );
}

void _unregister() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  if (gi.isRegistered<BatchParserService>()) {
    gi.unregister<BatchParserService>();
  }
  if (gi.isRegistered<ActivityReadProvider>()) {
    gi.unregister<ActivityReadProvider>();
  }
}

Widget _wrap(Widget child) {
  return MaterialApp(home: child);
}

void main() {
  setUpAll(() async {
  });

  tearDown(_unregister);

  group('ImportHistoryScreen — Clear all failed', () {
    testWidgets('header button hidden when no failed items', (tester) async {
      _registerFakes(_FakeApiClient());

      await tester.pumpWidget(_wrap(const ImportHistoryScreen()));
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.textContaining('Clear all failed'), findsNothing);
    });

    testWidgets('header button shows correct count when failed items exist',
        (tester) async {
      _registerFakes(_FakeApiClient(
        failedJobs: [
          {
            'id': 'job-1',
            'status': 'failed',
            'source_type': 'url',
            'total_items': 2,
            'created_at': _at(0),
          },
        ],
        failedItems: [
          {'id': 'item-1', 'status': 'failed', 'recipe_name': 'A'},
          {'id': 'item-2', 'status': 'failed', 'recipe_name': 'B'},
        ],
      ));

      await tester.pumpWidget(_wrap(const ImportHistoryScreen()));
      // Let initState's async _loadAttentionView finish
      for (var i = 0; i < 5; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }

      expect(find.text('Clear all failed (2)'), findsOneWidget);
    });

    testWidgets('tapping Clear all → cancel does not call API',
        (tester) async {
      final client = _FakeApiClient(
        failedJobs: [
          {
            'id': 'job-1',
            'status': 'failed',
            'source_type': 'url',
            'total_items': 1,
            'created_at': _at(0),
          },
        ],
        failedItems: [
          {'id': 'item-1', 'status': 'failed', 'recipe_name': 'A'},
        ],
      );
      _registerFakes(client);

      await tester.pumpWidget(_wrap(const ImportHistoryScreen()));
      for (var i = 0; i < 5; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }

      await tester.tap(find.text('Clear all failed (1)'));
      await tester.pump();
      await tester.pump();

      // Confirm dialog is visible
      expect(find.text('Dismiss all failed imports?'), findsOneWidget);

      await tester.tap(find.text('Cancel'));
      await tester.pump();
      await tester.pump();

      expect(client.dismissAllCalls, 0);
      // Row still there
      expect(find.text('Clear all failed (1)'), findsOneWidget);
    });

    testWidgets('tapping Clear all → confirm calls dismissAllFailedImports',
        (tester) async {
      final client = _FakeApiClient(
        failedJobs: [
          {
            'id': 'job-1',
            'status': 'failed',
            'source_type': 'url',
            'total_items': 1,
            'created_at': _at(0),
          },
        ],
        failedItems: [
          {'id': 'item-1', 'status': 'failed', 'recipe_name': 'A'},
        ],
      )..dismissAllCount = 1;
      _registerFakes(client);

      await tester.pumpWidget(_wrap(const ImportHistoryScreen()));
      for (var i = 0; i < 5; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }

      await tester.tap(find.text('Clear all failed (1)'));
      await tester.pump();
      await tester.pump();

      await tester.tap(find.text('Dismiss all'));
      // Drain the async dismiss call + setState + snackbar
      for (var i = 0; i < 5; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }

      expect(client.dismissAllCalls, 1);
      // Header button should now be gone (0 failed items)
      expect(find.textContaining('Clear all failed'), findsNothing);
      // Snackbar confirmation
      expect(find.textContaining('Dismissed'), findsOneWidget);
    });
  });
}
