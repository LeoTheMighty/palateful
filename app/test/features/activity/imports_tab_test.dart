import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/activity/imports_tab.dart';
import 'package:palateful/features/activity/providers/activity_read_provider.dart';
import 'package:palateful/features/activity/widgets/import_row.dart';

Response<dynamic> _fakeResponse(dynamic data, {int status = 200}) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: status,
    );

class _FakeApiClient extends ApiClient {
  /// Raw jobs keyed by their status query param. Tests seed this.
  final Map<String, List<dynamic>> jobsByStatus;

  /// Items keyed by parent job id.
  final Map<String, List<dynamic>> itemsByJobId;

  final List<String> archiveCalls = [];
  final List<String> unarchiveCalls = [];
  bool archiveThrows = false;
  int archiveErrorStatus = 500;

  _FakeApiClient({
    this.jobsByStatus = const {},
    this.itemsByJobId = const {},
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
    if (archivedOnly) {
      return _fakeResponse({
        'jobs': jobsByStatus['__archived__'] ?? const [],
        'next_cursor': null,
      });
    }
    if (status == null) {
      // Union of every non-archived bucket. The production tab fetches
      // all non-archived jobs in one call and buckets items client-side
      // by item.status.
      final all = <dynamic>[
        for (final entry in jobsByStatus.entries)
          if (entry.key != '__archived__') ...entry.value,
      ];
      return _fakeResponse({'jobs': all});
    }
    final jobs = jobsByStatus[status] ?? const [];
    return _fakeResponse({'jobs': jobs});
  }

  @override
  Future<Response> listImportItems(
    String jobId, {
    String? status,
    bool includeArchived = false,
  }) async {
    return _fakeResponse({'items': itemsByJobId[jobId] ?? const []});
  }

  @override
  Future<Response> listImportItemsBatch(
    List<String> jobIds, {
    String? status,
    bool includeArchived = false,
  }) async {
    final out = <dynamic>[];
    for (final jobId in jobIds) {
      final items = itemsByJobId[jobId] ?? const [];
      for (final item in items) {
        // Backend stamps job_id on every row; mirror that here so the
        // client's grouping logic sees the same shape as production.
        out.add({...item as Map<String, dynamic>, 'job_id': jobId});
      }
    }
    return _fakeResponse({'items': out});
  }

  @override
  Future<Response> getImportItemsSeeAllCount() async =>
      _fakeResponse(
          {'archived': 0, 'read_and_old_completed': 0, 'total': 0});

  @override
  Future<Response> archiveImportItem(String id) async {
    archiveCalls.add(id);
    if (archiveThrows) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/import-items/$id/archive'),
        response: Response(
          requestOptions: RequestOptions(path: ''),
          statusCode: archiveErrorStatus,
        ),
      );
    }
    return _fakeResponse({'id': id, 'archived_at': '2026-04-18T12:00:00Z'});
  }

  @override
  Future<Response> unarchiveImportItem(String id) async {
    unarchiveCalls.add(id);
    return _fakeResponse({'id': id, 'archived_at': null});
  }
}

void _register(_FakeApiClient client) {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  gi.registerSingleton<ApiClient>(client);
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
  if (gi.isRegistered<ActivityReadProvider>()) {
    gi.unregister<ActivityReadProvider>();
  }
}

Widget _wrap(Widget child) => ProviderScope(
      child: MaterialApp(home: Scaffold(body: child)),
    );

/// Build a router around ImportsTab so `context.push('/…')` can be
/// asserted on per-state tap-destination tests.
Widget _wrapWithRouter({String? logSink}) {
  final navLog = <String>[];
  final router = GoRouter(
    initialLocation: '/',
    routes: [
      GoRoute(
        path: '/',
        builder: (_, _) => const Scaffold(body: ImportsTab()),
      ),
      GoRoute(
        path: '/recipes/:id',
        builder: (_, state) {
          navLog.add('/recipes/${state.pathParameters['id']}');
          return Scaffold(body: Text('RECIPE-${state.pathParameters['id']}'));
        },
      ),
      GoRoute(
        path: '/recipes/import/review/:itemId',
        builder: (_, state) {
          navLog.add('/recipes/import/review/${state.pathParameters['itemId']}');
          return Scaffold(
            body: Text('REVIEW-${state.pathParameters['itemId']}'),
          );
        },
      ),
      GoRoute(
        path: '/recipes/import/review-list/:jobId',
        builder: (_, state) {
          navLog.add('/recipes/import/review-list/${state.pathParameters['jobId']}');
          return Scaffold(
            body: Text('JOB-${state.pathParameters['jobId']}'),
          );
        },
      ),
    ],
  );
  // Stash the nav log on the router's refresh listenable via a key-able
  // static; tests capture via a closure shared at test scope. (Keep it
  // simple: since each test sets up its own router, they pass the log
  // list in as a shared ref.)
  _lastNavLog = navLog;
  return ProviderScope(child: MaterialApp.router(routerConfig: router));
}

List<String> _lastNavLog = [];

void main() {
  setUpAll(() async {
  });

  tearDown(_unregister);

  testWidgets('empty state renders "All clear — no imports yet"',
      (tester) async {
    final api = _FakeApiClient();
    _register(api);

    await tester.pumpWidget(_wrap(const ImportsTab()));
    // Can't use pumpAndSettle here — the in-progress row's
    // CircularProgressIndicator is an infinite animation.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('All clear — no imports yet'), findsOneWidget);
  });

  testWidgets('renders all four sections with one row each', (tester) async {
    final api = _FakeApiClient(
      jobsByStatus: {
        'processing': [
          {
            'id': 'job-ip',
            'status': 'processing',
            'source_type': 'url',
            'source_url': 'https://example.com/recipe',
            'total_items': 2,
            'processed_items': 1,
            'created_at': '2026-04-18T10:00:00Z',
          },
        ],
        'awaiting_review': [
          {
            'id': 'job-r',
            'status': 'awaiting_review',
            'source_type': 'photo',
            'created_at': '2026-04-18T10:10:00Z',
          },
        ],
        'failed': [
          {
            'id': 'job-f',
            'status': 'failed',
            'source_type': 'url',
            'created_at': '2026-04-18T10:20:00Z',
          },
        ],
        'completed': [
          {
            'id': 'job-c',
            'status': 'completed',
            'source_type': 'url',
            'created_at': '2026-04-18T10:30:00Z',
          },
        ],
      },
      itemsByJobId: {
        'job-r': [
          {
            'id': 'item-review',
            'status': 'awaiting_review',
            'recipe_name': 'Review me',
            'source_type': 'photo',
            'created_at': '2026-04-18T10:15:00Z',
          },
        ],
        'job-f': [
          {
            'id': 'item-failed',
            'status': 'failed',
            'recipe_name': 'I died',
            'source_type': 'url',
            'error_message': 'boom',
            'created_at': '2026-04-18T10:25:00Z',
          },
        ],
        'job-c': [
          {
            'id': 'item-done',
            'status': 'completed',
            'recipe_name': 'Green goodness',
            'source_type': 'url',
            'created_recipe_id': 'recipe-42',
            'created_at': '2026-04-18T10:35:00Z',
          },
        ],
      },
    );
    _register(api);

    await tester.pumpWidget(_wrap(const ImportsTab()));
    // Can't use pumpAndSettle here — the in-progress row's
    // CircularProgressIndicator is an infinite animation.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.textContaining('In Progress · 1'), findsOneWidget);
    expect(find.textContaining('Needs Review · 1'), findsOneWidget);
    expect(find.textContaining('Failed · 1'), findsOneWidget);
    expect(find.textContaining('Auto-Imported · 1'), findsOneWidget);

    expect(find.text('Review me'), findsOneWidget);
    expect(find.text('I died'), findsOneWidget);
    expect(find.text('Green goodness'), findsOneWidget);
  });

  testWidgets('blue rows have no Dismissible wrapper; swipe is a no-op',
      (tester) async {
    final api = _FakeApiClient(jobsByStatus: {
      'processing': [
        {
          'id': 'job-ip',
          'status': 'processing',
          'source_type': 'url',
          'source_url': 'https://example.com/recipe',
          'total_items': 2,
          'processed_items': 1,
          'created_at': '2026-04-18T10:00:00Z',
        },
      ],
    });
    _register(api);

    await tester.pumpWidget(_wrap(const ImportsTab()));
    // Can't use pumpAndSettle here — the in-progress row's
    // CircularProgressIndicator is an infinite animation.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 100));

    // No Dismissible has been rendered — only the bare ImportRow.
    expect(find.byType(Dismissible), findsNothing);
    expect(find.byType(ImportRow), findsOneWidget);

    // Dragging does nothing — no archive API fires.
    await tester.drag(find.byType(ImportRow), const Offset(-500, 0));
    await tester.pump(const Duration(milliseconds: 200));
    expect(api.archiveCalls, isEmpty);
  });

  testWidgets('non-blue swipe archives + fires API', (tester) async {
    final api = _FakeApiClient(
      jobsByStatus: {
        'awaiting_review': [
          {
            'id': 'job-r',
            'status': 'awaiting_review',
            'source_type': 'photo',
            'created_at': '2026-04-18T10:10:00Z',
          },
        ],
      },
      itemsByJobId: {
        'job-r': [
          {
            'id': 'item-review',
            'status': 'awaiting_review',
            'recipe_name': 'Swipe me',
            'source_type': 'photo',
            'created_at': '2026-04-18T10:15:00Z',
          },
        ],
      },
    );
    _register(api);

    await tester.pumpWidget(_wrap(const ImportsTab()));
    // Can't use pumpAndSettle here — the in-progress row's
    // CircularProgressIndicator is an infinite animation.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 100));

    await tester.drag(find.byType(Dismissible).first, const Offset(-500, 0));
    await tester.pumpAndSettle();

    expect(api.archiveCalls, equals(['item-review']));
    expect(find.text('Swipe me'), findsNothing);
    expect(find.text('Dismissed'), findsOneWidget);
    expect(find.text('Undo'), findsOneWidget);
  });

  testWidgets('409 on swipe shows the in-progress message + restores',
      (tester) async {
    final api = _FakeApiClient(
      jobsByStatus: {
        'awaiting_review': [
          {
            'id': 'job-r',
            'status': 'awaiting_review',
            'source_type': 'photo',
            'created_at': '2026-04-18T10:10:00Z',
          },
        ],
      },
      itemsByJobId: {
        'job-r': [
          {
            'id': 'item-review',
            'status': 'awaiting_review',
            'recipe_name': 'Flipped mid-swipe',
            'source_type': 'photo',
            'created_at': '2026-04-18T10:15:00Z',
          },
        ],
      },
    )
      ..archiveThrows = true
      ..archiveErrorStatus = 409;
    _register(api);

    await tester.pumpWidget(_wrap(const ImportsTab()));
    // Can't use pumpAndSettle here — the in-progress row's
    // CircularProgressIndicator is an infinite animation.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 100));

    await tester.drag(find.byType(Dismissible).first, const Offset(-500, 0));
    // Pump a bunch of frames: Dismissible resize animation (~400ms) +
    // microtask drain for the thrown DioException + the snackbar swap.
    for (var i = 0; i < 20; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }

    expect(api.archiveCalls, equals(['item-review']));
    expect(find.text("Can't dismiss while importing"), findsOneWidget);
    expect(find.text('Flipped mid-swipe'), findsOneWidget);
  });

  testWidgets('green row taps navigate to /recipes/:id', (tester) async {
    final api = _FakeApiClient(
      jobsByStatus: {
        'completed': [
          {
            'id': 'job-c',
            'status': 'completed',
            'source_type': 'url',
            'created_at': '2026-04-18T10:30:00Z',
          },
        ],
      },
      itemsByJobId: {
        'job-c': [
          {
            'id': 'item-done',
            'status': 'completed',
            'recipe_name': 'Ship it',
            'source_type': 'url',
            'created_recipe_id': 'recipe-42',
            'created_at': '2026-04-18T10:35:00Z',
          },
        ],
      },
    );
    _register(api);
    _lastNavLog.clear();

    await tester.pumpWidget(_wrapWithRouter());
    await tester.pumpAndSettle();

    await tester.tap(find.text('Ship it'));
    await tester.pumpAndSettle();

    expect(_lastNavLog, contains('/recipes/recipe-42'));
  });

  testWidgets(
      'buckets by item.status — items still render when parent job.status '
      'differs',
      (tester) async {
    // Regression for the 2026-04-20 bug: the tab used to require
    // (job.status == section_status && item.status == section_status).
    // A `completed` job containing a `failed` item made that item
    // invisible; same for every other mismatch. Bucketing by item.status
    // is now the contract.
    final api = _FakeApiClient(
      jobsByStatus: {
        // Job.status=awaiting_review, but the only item inside is
        // actually failed — must land in the Failed section.
        'awaiting_review': [
          {
            'id': 'job-ar-holding-failed',
            'status': 'awaiting_review',
            'source_type': 'photo',
            'created_at': '2026-04-18T10:10:00Z',
          },
        ],
        // Job.status=completed, but items inside have mixed statuses.
        'completed': [
          {
            'id': 'job-c-mixed',
            'status': 'completed',
            'source_type': 'url',
            'created_at': '2026-04-18T10:30:00Z',
          },
        ],
      },
      itemsByJobId: {
        'job-ar-holding-failed': [
          {
            'id': 'item-buried-failed',
            'status': 'failed',
            'recipe_name': 'Buried failure',
            'source_type': 'photo',
            'error_message': 'boom',
            'created_at': '2026-04-18T10:15:00Z',
          },
        ],
        'job-c-mixed': [
          {
            'id': 'item-buried-review',
            'status': 'awaiting_review',
            'recipe_name': 'Buried review',
            'source_type': 'url',
            'created_at': '2026-04-18T10:31:00Z',
          },
          {
            'id': 'item-done',
            'status': 'completed',
            'recipe_name': 'Done',
            'source_type': 'url',
            'created_recipe_id': 'recipe-42',
            'created_at': '2026-04-18T10:32:00Z',
          },
          {
            'id': 'item-skip',
            'status': 'skipped',
            'recipe_name': 'Skipped photo',
            'source_type': 'photo',
            'created_at': '2026-04-18T10:33:00Z',
          },
        ],
      },
    );
    _register(api);

    await tester.pumpWidget(_wrap(const ImportsTab()));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 100));

    // Every item surfaces even though the parent job.status doesn't
    // match the section. This is the exact pattern that went invisible
    // in prod.
    expect(find.text('Buried failure'), findsOneWidget);
    expect(find.text('Buried review'), findsOneWidget);
    expect(find.text('Done'), findsOneWidget);
    expect(find.text('Skipped photo'), findsOneWidget);
    expect(find.textContaining('Skipped · 1'), findsOneWidget);
    expect(find.textContaining('Failed · 1'), findsOneWidget);
    expect(find.textContaining('Needs Review · 1'), findsOneWidget);
    expect(find.textContaining('Auto-Imported · 1'), findsOneWidget);
  });

  testWidgets('yellow row taps navigate to review screen', (tester) async {
    final api = _FakeApiClient(
      jobsByStatus: {
        'awaiting_review': [
          {
            'id': 'job-r',
            'status': 'awaiting_review',
            'source_type': 'photo',
            'created_at': '2026-04-18T10:10:00Z',
          },
        ],
      },
      itemsByJobId: {
        'job-r': [
          {
            'id': 'item-review',
            'status': 'awaiting_review',
            'recipe_name': 'Tap for review',
            'source_type': 'photo',
            'created_at': '2026-04-18T10:15:00Z',
          },
        ],
      },
    );
    _register(api);
    _lastNavLog.clear();

    await tester.pumpWidget(_wrapWithRouter());
    await tester.pumpAndSettle();

    await tester.tap(find.text('Tap for review'));
    await tester.pumpAndSettle();

    expect(_lastNavLog, contains('/recipes/import/review/item-review'));
  });
}
