import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/activity/import_history_screen.dart';
import 'package:palateful/features/activity/providers/activity_read_provider.dart';
import 'package:palateful/features/recipes/add_recipe/batch_parser_service.dart';

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
  }) async {
    if (status == 'failed') {
      return _fakeResponse({'jobs': failedJobs});
    }
    return _fakeResponse({'jobs': []});
  }

  @override
  Future<Response> listImportItems(String jobId, {String? status}) async {
    return _fakeResponse({'items': failedItems});
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
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
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
            'created_at': '2026-04-15T12:00:00Z',
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
            'created_at': '2026-04-15T12:00:00Z',
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
            'created_at': '2026-04-15T12:00:00Z',
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
