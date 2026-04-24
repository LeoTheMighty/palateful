import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/activity/widgets/see_all_footer.dart';

Response<dynamic> _fakeResponse(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

/// A queued page of the paginated archived-jobs fetch: each page
/// returns a list of `{job, items}` pairs. The fake client serves
/// them in order.
class _Page {
  final List<Map<String, dynamic>> jobs;
  final Map<String, List<Map<String, dynamic>>> itemsByJobId;
  final String? nextCursor;

  _Page({
    required this.jobs,
    required this.itemsByJobId,
    required this.nextCursor,
  });

  factory _Page.build({
    required String prefix,
    required int jobCount,
    required int itemsPerJob,
    String? nextCursor,
  }) {
    final jobs = <Map<String, dynamic>>[];
    final items = <String, List<Map<String, dynamic>>>{};
    for (var j = 0; j < jobCount; j++) {
      final jobId = '$prefix-job-$j';
      jobs.add({
        'id': jobId,
        'status': 'completed',
        'source_type': 'url',
        'total_items': itemsPerJob,
        'succeeded_items': itemsPerJob,
        'failed_items': 0,
        'pending_review_items': 0,
        'recipe_book_id': 'bk',
        'created_at': '2026-01-01T00:00:00Z',
        'archived_at': '2026-02-01T00:00:00Z',
      });
      items[jobId] = List.generate(itemsPerJob, (i) {
        return {
          'id': '$jobId-item-$i',
          'status': 'completed',
          'source_type': 'url',
          'recipe_name': '$prefix row $j-$i',
          'created_at': '2026-01-01T00:00:00Z',
          'archived_at': '2026-02-01T00:00:00Z',
        };
      });
    }
    return _Page(
      jobs: jobs,
      itemsByJobId: items,
      nextCursor: nextCursor,
    );
  }
}

class _FakeApiClient extends ApiClient {
  final List<_Page> pagesToReturn;
  int countArchived;
  int countOther;
  final List<String> unarchiveCalls = [];
  bool unarchiveThrows = false;
  bool failPage = false;
  final List<String?> jobCursorsSeen = [];

  _FakeApiClient({
    required this.pagesToReturn,
    this.countArchived = 0,
    this.countOther = 0,
  });

  @override
  Future<Response> getImportItemsSeeAllCount() async {
    return _fakeResponse({
      'archived': countArchived,
      'read_and_old_completed': countOther,
      'total': countArchived + countOther,
    });
  }

  @override
  Future<Response> listImportJobs({
    String? status,
    int limit = 20,
    int offset = 0,
    bool includeArchived = false,
    bool archivedOnly = false,
    String? cursor,
  }) async {
    jobCursorsSeen.add(cursor);
    if (failPage) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/import-jobs'),
        response: Response(
          requestOptions: RequestOptions(path: ''),
          statusCode: 500,
        ),
      );
    }
    if (pagesToReturn.isEmpty) {
      return _fakeResponse({'jobs': <dynamic>[], 'next_cursor': null});
    }
    final page = pagesToReturn.removeAt(0);
    return _fakeResponse({
      'jobs': page.jobs,
      'next_cursor': page.nextCursor,
    });
  }

  @override
  Future<Response> listImportItems(
    String jobId, {
    String? status,
    bool includeArchived = false,
  }) async {
    // Lookup across all queued pages' items. (Even already-consumed
    // pages keep their items referenced via the fake — simpler than
    // tracking consumed state explicitly.)
    // We keep a shared map built in setup.
    final items = _itemsByJobId[jobId] ?? const <Map<String, dynamic>>[];
    return _fakeResponse({'items': items});
  }

  @override
  Future<Response> listImportItemsBatch(
    List<String> jobIds, {
    String? status,
    bool includeArchived = false,
  }) async {
    final out = <dynamic>[];
    for (final jobId in jobIds) {
      final items = _itemsByJobId[jobId] ?? const <Map<String, dynamic>>[];
      for (final item in items) {
        out.add({...item, 'job_id': jobId});
      }
    }
    return _fakeResponse({'items': out});
  }

  final Map<String, List<Map<String, dynamic>>> _itemsByJobId = {};

  @override
  Future<Response> unarchiveImportItem(String id) async {
    unarchiveCalls.add(id);
    if (unarchiveThrows) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/import-items/$id/unarchive'),
        response: Response(
          requestOptions: RequestOptions(path: ''),
          statusCode: 500,
        ),
      );
    }
    return _fakeResponse({'id': id, 'archived_at': null});
  }

  @override
  Future<Response> archiveImportItem(String id) async {
    return _fakeResponse({'id': id, 'archived_at': '2026-04-18T12:00:00Z'});
  }
}

void _register(_FakeApiClient client) {
  // Build the shared items index once so listImportItems can resolve
  // by jobId across multiple pages.
  for (final p in client.pagesToReturn) {
    client._itemsByJobId.addAll(p.itemsByJobId);
  }
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  gi.registerSingleton<ApiClient>(client);
}

void _unregister() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
}

Widget _wrap(Widget child) => ProviderScope(
      child: MaterialApp(
        home: Scaffold(body: ListView(children: [child])),
      ),
    );

void main() {
  setUpAll(() async {
  });

  tearDown(_unregister);

  testWidgets('count=0 renders nothing', (tester) async {
    _register(_FakeApiClient(pagesToReturn: const []));
    await tester.pumpWidget(_wrap(const SeeAllFooter()));
    await tester.pumpAndSettle();

    expect(find.textContaining('See all'), findsNothing);
  });

  testWidgets('expands and loads page 1 of archived jobs', (tester) async {
    final api = _FakeApiClient(
      countArchived: 6,
      countOther: 0,
      pagesToReturn: [
        _Page.build(prefix: 'p1', jobCount: 3, itemsPerJob: 2, nextCursor: null),
      ],
    );
    _register(api);

    await tester.pumpWidget(_wrap(const SeeAllFooter()));
    await tester.pumpAndSettle();

    expect(find.text('See all (6)'), findsOneWidget);

    await tester.tap(find.text('See all (6)'));
    await tester.pumpAndSettle();

    // 6 rows across 3 jobs.
    expect(find.text('p1 row 0-0'), findsOneWidget);
    expect(find.text('p1 row 2-1'), findsOneWidget);
    expect(api.jobCursorsSeen, [null]);
    expect(find.text("That's everything. (6 total)"), findsOneWidget);
  });

  testWidgets('scrolling to end triggers the next-page cursor fetch',
      (tester) async {
    // Oversize the first page (100 items) so the rendered content
    // exceeds the test viewport (~600px). A scrollable with
    // maxScrollExtent > 0 is required for the ancestor-scroll listener
    // to fire — the widget uses `pos.pixels >= pos.maxScrollExtent-200`
    // and scroll events don't dispatch on a non-scrolling parent.
    final api = _FakeApiClient(
      countArchived: 100,
      countOther: 0,
      pagesToReturn: [
        _Page.build(
            prefix: 'p1', jobCount: 20, itemsPerJob: 5, nextCursor: 'CURSOR2'),
        _Page.build(
            prefix: 'p2', jobCount: 2, itemsPerJob: 2, nextCursor: null),
      ],
    );
    _register(api);

    await tester.pumpWidget(_wrap(const SeeAllFooter()));
    await tester.pumpAndSettle();
    await tester.tap(find.text('See all (100)'));
    await tester.pumpAndSettle();

    // Scroll the outer ListView to the bottom to trigger the next page.
    await tester.drag(find.byType(ListView), const Offset(0, -8000));
    await tester.pumpAndSettle();

    expect(api.jobCursorsSeen, equals([null, 'CURSOR2']));
    expect(find.text('p2 row 0-0'), findsOneWidget);
  });

  testWidgets('failed page fetch renders retry row; tap retries',
      (tester) async {
    // Fail the FIRST fetch — initial-load error path. Retry row should
    // render in place of the initial spinner. Small fixture is fine
    // because the error row renders even with zero rows loaded.
    final api = _FakeApiClient(
      countArchived: 6,
      countOther: 0,
      pagesToReturn: [],
    );
    _register(api);
    api.failPage = true;

    await tester.pumpWidget(_wrap(const SeeAllFooter()));
    await tester.pumpAndSettle();
    await tester.tap(find.text('See all (6)'));
    await tester.pumpAndSettle();

    expect(find.text("Couldn't load more. Tap to retry."), findsOneWidget);

    // Recover: queue a successful page and clear the failure flag.
    api.failPage = false;
    final recoverPage = _Page.build(
        prefix: 'r1', jobCount: 1, itemsPerJob: 1, nextCursor: null);
    api.pagesToReturn.add(recoverPage);
    api._itemsByJobId.addAll(recoverPage.itemsByJobId);

    await tester.tap(find.text("Couldn't load more. Tap to retry."));
    await tester.pumpAndSettle();

    expect(find.text('r1 row 0-0'), findsOneWidget);
    expect(find.text("Couldn't load more. Tap to retry."), findsNothing);
  });

  testWidgets('swipe-right unarchives and fires API', (tester) async {
    final api = _FakeApiClient(
      countArchived: 1,
      countOther: 0,
      pagesToReturn: [
        _Page.build(prefix: 'solo', jobCount: 1, itemsPerJob: 1, nextCursor: null),
      ],
    );
    _register(api);

    await tester.pumpWidget(_wrap(const SeeAllFooter()));
    await tester.pumpAndSettle();
    await tester.tap(find.text('See all (1)'));
    await tester.pumpAndSettle();

    await tester.drag(find.byType(Dismissible).first, const Offset(500, 0));
    await tester.pumpAndSettle();

    expect(api.unarchiveCalls, equals(['solo-job-0-item-0']));
    expect(find.text('Unarchived'), findsOneWidget);
    expect(find.text('Undo'), findsOneWidget);
  });
}
