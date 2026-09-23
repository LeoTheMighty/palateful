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

  /// Parser batches returned by `listParserBatches`. impvis1: a photo
  /// import is a ParserBatch before it fans out into ImportJobs, and the
  /// tab could not see that state at all.
  final List<dynamic> parserBatches;

  final List<bool> parserBatchCalls = [];
  bool parserBatchesThrow = false;

  _FakeApiClient({
    this.jobsByStatus = const {},
    this.itemsByJobId = const {},
    this.parserBatches = const [],
  });

  @override
  Future<Response> listParserBatches({
    bool activeOnly = false,
    int limit = 20,
  }) async {
    parserBatchCalls.add(activeOnly);
    if (parserBatchesThrow) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/parser/batches'),
        response: Response(
          requestOptions: RequestOptions(path: ''),
          statusCode: 503,
        ),
      );
    }
    return _fakeResponse({'batches': parserBatches});
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

/// Base instant for every fixture timestamp in this file.
///
/// Fixtures MUST stay inside the tab's 30-day recency window: `imports_tab`
/// drops `completed` + `skipped` items older than the cutoff (they stay
/// reachable via See-all), while `awaiting_review` + `failed` are exempt
/// because they're actionable. Absolute dates therefore rot silently — once
/// they aged past 30 days the Auto-Imported and Skipped sections stopped
/// rendering and three tests went red, months after the commit that "broke"
/// them (imptab1). Anchor to `now` so they can't rot again.
final DateTime _fixtureBase =
    DateTime.now().toUtc().subtract(const Duration(hours: 2));

/// A fixture timestamp `minutesAfterBase` past [_fixtureBase]. Offsets
/// preserve the original fixtures' relative ordering, which the
/// created-at-descending sort assertions depend on.
String _at(int minutesAfterBase) =>
    _fixtureBase.add(Duration(minutes: minutesAfterBase)).toIso8601String();

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
            'created_at': _at(0),
          },
        ],
        'awaiting_review': [
          {
            'id': 'job-r',
            'status': 'awaiting_review',
            'source_type': 'photo',
            'created_at': _at(10),
          },
        ],
        'failed': [
          {
            'id': 'job-f',
            'status': 'failed',
            'source_type': 'url',
            'created_at': _at(20),
          },
        ],
        'completed': [
          {
            'id': 'job-c',
            'status': 'completed',
            'source_type': 'url',
            'created_at': _at(30),
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
            'created_at': _at(15),
          },
        ],
        'job-f': [
          {
            'id': 'item-failed',
            'status': 'failed',
            'recipe_name': 'I died',
            'source_type': 'url',
            'error_message': 'boom',
            'created_at': _at(25),
          },
        ],
        'job-c': [
          {
            'id': 'item-done',
            'status': 'completed',
            'recipe_name': 'Green goodness',
            'source_type': 'url',
            'created_recipe_id': 'recipe-42',
            'created_at': _at(35),
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
          'created_at': _at(0),
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
            'created_at': _at(10),
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
            'created_at': _at(15),
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
            'created_at': _at(10),
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
            'created_at': _at(15),
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
            'created_at': _at(30),
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
            'created_at': _at(35),
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
            'created_at': _at(10),
          },
        ],
        // Job.status=completed, but items inside have mixed statuses.
        'completed': [
          {
            'id': 'job-c-mixed',
            'status': 'completed',
            'source_type': 'url',
            'created_at': _at(30),
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
            'created_at': _at(15),
          },
        ],
        'job-c-mixed': [
          {
            'id': 'item-buried-review',
            'status': 'awaiting_review',
            'recipe_name': 'Buried review',
            'source_type': 'url',
            'created_at': _at(31),
          },
          {
            'id': 'item-done',
            'status': 'completed',
            'recipe_name': 'Done',
            'source_type': 'url',
            'created_recipe_id': 'recipe-42',
            'created_at': _at(32),
          },
          {
            'id': 'item-skip',
            'status': 'skipped',
            'recipe_name': 'Skipped photo',
            'source_type': 'photo',
            'created_at': _at(33),
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

  // ---------------------------------------------------------------
  // impvis1 — the pending cases. NOTHING above this line covered an
  // import that is still in flight: every in-progress fixture used job
  // status `processing`, no fixture used item status `pending`, and no
  // test touched the parser-batch source at all. That is why Leo's
  // "1 import in progress, empty tab" survived to production.
  // ---------------------------------------------------------------

  testWidgets('a pre-fan-out parser batch renders In Progress (impvis1)',
      (tester) async {
    // The exact state Leo hit: the Add Recipe strip counts this batch
    // from /v1/parser/batches while jobs and items are both empty.
    final client = _FakeApiClient(
      jobsByStatus: const {},
      itemsByJobId: const {},
      parserBatches: [
        {
          'id': 'batch-1',
          'status': 'running',
          'group_count': 3,
          'recipe_book_id': null,
          // Inside ImportBatch.preFanOutGrace (_fixtureBase is now-2h,
          // which is exactly the boundary).
          'created_at': _at(115),
          'completed_at': null,
          'error_message': null,
          'jobs': const [],
          'import_jobs': const [],
        },
      ],
    );
    _register(client);

    await tester.pumpWidget(_wrap(const ImportsTab()));
    // Not pumpAndSettle: the in-progress row's progress indicator animates
    // forever, so it never settles (same reason as the four-section test).
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('All clear — no imports yet'), findsNothing,
        reason: 'the batch exists, so the tab is not empty');
    expect(find.text('Importing 0 of 3'), findsOneWidget);
    expect(client.parserBatchCalls, contains(true),
        reason: 'the tab asks for active batches only');
  });

  testWidgets('a fanned-out batch does not double-count its jobs (impvis1)',
      (tester) async {
    // Once the batch has produced an ImportJob, that job is already in the
    // jobs list — a synthesised batch row on top would show one import
    // twice.
    final client = _FakeApiClient(
      jobsByStatus: {
        'processing': [
          {
            'id': 'job-1',
            'status': 'processing',
            'source_type': 'photo',
            'total_items': 2,
            // No `processed_items`: ListImportJobs.JobSummary does not send
            // it (list_import_jobs.py), so a fixture that includes it tests
            // a response shape production never produces. Every blue row
            // really does read "Importing 0 of N" — filed as impprog1.
            'created_at': _at(1),
          },
        ],
      },
      parserBatches: [
        {
          'id': 'batch-1',
          'status': 'running',
          'group_count': 2,
          'recipe_book_id': null,
          'created_at': _at(0),
          'completed_at': null,
          'error_message': null,
          'jobs': const [],
          'import_jobs': const [
            {'id': 'job-1', 'status': 'processing'},
          ],
        },
      ],
    );
    _register(client);

    await tester.pumpWidget(_wrap(const ImportsTab()));
    // Not pumpAndSettle: the in-progress row's progress indicator animates
    // forever, so it never settles (same reason as the four-section test).
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.byType(ImportRow), findsOneWidget);
    expect(find.text('Importing 0 of 2'), findsOneWidget);
  });

  testWidgets('a batch that never fanned out ages out (impvis1)',
      (tester) async {
    // parser_batch_completion.py:133-141 ends a batch as `partial` with NO
    // ImportJobs when it has no recipe_book_id and an OCR job failed, and
    // nothing sweeps ParserBatch rows. Without an age cap that batch counts
    // — and, since this story, renders — for the life of the account.
    final client = _FakeApiClient(
      parserBatches: [
        {
          'id': 'batch-old',
          'status': 'partial',
          'group_count': 2,
          'recipe_book_id': null,
          'created_at': DateTime.now()
              .toUtc()
              .subtract(const Duration(days: 3))
              .toIso8601String(),
          'completed_at': null,
          'error_message': null,
          'jobs': const [],
          'import_jobs': const [],
        },
      ],
    );
    _register(client);

    await tester.pumpWidget(_wrap(const ImportsTab()));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 100));

    // Not hidden — said plainly. parsercap1 measured the real case: the
    // batch's AWS Batch job never started, died on
    // `instance-terminated-no-capacity`, and produced zero ImportJobs.
    // Nothing server-side marks the batch failed, so it still reads
    // `submitted`; hiding it would leave Leo with silence, and rendering
    // it In Progress would be a spinner that never stops.
    expect(find.text('All clear — no imports yet'), findsNothing);
    expect(find.text('Import failed — the parser never started'),
        findsOneWidget);
    expect(find.text('2 photos'), findsOneWidget);
  });

  testWidgets('a stalled batch row cannot be tapped or swiped (impvis1)',
      (tester) async {
    // There is no ImportJob to open and no ImportItem to archive — the
    // rows behind it were never created.
    final client = _FakeApiClient(
      parserBatches: [
        {
          'id': 'batch-dead',
          'status': 'submitted',
          'group_count': 1,
          'recipe_book_id': null,
          'created_at': DateTime.now()
              .toUtc()
              .subtract(const Duration(hours: 5))
              .toIso8601String(),
          'completed_at': null,
          'error_message': null,
          'jobs': const [],
          'import_jobs': const [],
        },
      ],
    );
    _register(client);

    await tester.pumpWidget(_wrap(const ImportsTab()));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.byType(Dismissible), findsNothing);
    await tester.tap(find.text('Import failed — the parser never started'));
    await tester.pump();
    // No navigation, no exception.
    expect(find.text('Import failed — the parser never started'),
        findsOneWidget);
  });

  testWidgets('stragglers collapse to ONE row per job (impvis1)',
      (tester) async {
    // create_recipe_task.py:465-483 flips a job to `awaiting_review` as
    // soon as one item needs review, with the rest still `pending`. One row
    // per straggling item turned a bulk import into dozens of rows and
    // broke this section's job-granularity rule.
    final client = _FakeApiClient(
      jobsByStatus: {
        'awaiting_review': [
          {
            'id': 'job-bulk',
            'status': 'awaiting_review',
            'source_type': 'url',
            'total_items': 6,
            'processed_items': 1,
            'created_at': _at(0),
          },
        ],
      },
      itemsByJobId: {
        'job-bulk': [
          for (var i = 0; i < 5; i++)
            {
              'id': 'item-$i',
              'status': 'pending',
              'source_type': 'url',
              'created_at': _at(i + 1),
            },
          {
            'id': 'item-review',
            'status': 'awaiting_review',
            'recipe_name': 'Needs a look',
            'source_type': 'url',
            'created_at': _at(9),
          },
        ],
      },
    );
    _register(client);

    await tester.pumpWidget(_wrap(const ImportsTab()));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 100));

    // One blue row for the five stragglers, one yellow row for the item
    // that needs review — not five blue rows.
    expect(find.text('Importing 0 of 5'), findsOneWidget);
    expect(find.byType(ImportRow), findsNWidgets(2));
  });

  testWidgets('a cancelled import does not render its leftovers (impvis1)',
      (tester) async {
    // cancel_import_job.py:59-61 leaves the items alone. They are
    // abandoned, not in flight — a progress ring on them would be a lie.
    final client = _FakeApiClient(
      jobsByStatus: {
        'cancelled': [
          {
            'id': 'job-x',
            'status': 'cancelled',
            'source_type': 'url',
            'total_items': 3,
            'processed_items': 0,
            'created_at': _at(0),
          },
        ],
      },
      itemsByJobId: {
        'job-x': [
          {
            'id': 'item-abandoned',
            'status': 'pending',
            'source_type': 'url',
            'created_at': _at(1),
          },
        ],
      },
    );
    _register(client);

    await tester.pumpWidget(_wrap(const ImportsTab()));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('All clear — no imports yet'), findsOneWidget);
  });

  testWidgets('a pending job renders In Progress (impvis1)', (tester) async {
    // Every prior in-progress fixture used `processing`. A job that has
    // been accepted but never picked up sits in `pending` — the state a
    // lost Celery dispatch leaves behind, and the one Leo would call
    // "pending".
    final client = _FakeApiClient(
      jobsByStatus: {
        'pending': [
          {
            'id': 'job-p',
            'status': 'pending',
            'source_type': 'url',
            'source_url': 'https://example.com/r',
            'total_items': 1,
            'processed_items': 0,
            'created_at': _at(0),
          },
        ],
      },
    );
    _register(client);

    await tester.pumpWidget(_wrap(const ImportsTab()));
    // Not pumpAndSettle: the in-progress row's progress indicator animates
    // forever, so it never settles (same reason as the four-section test).
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('All clear — no imports yet'), findsNothing);
    expect(find.text('Importing 0 of 1'), findsOneWidget);
  });

  testWidgets('a pending item under a finished job still renders (impvis1)',
      (tester) async {
    // Item statuses pending/extracting/matching fell through `default:
    // break` and were visible only via the parent job's Blue row. When the
    // parent has moved on, nothing rendered them — while the server's
    // imports_actionable counted every one.
    final client = _FakeApiClient(
      jobsByStatus: {
        'completed': [
          {
            'id': 'job-c',
            'status': 'completed',
            'source_type': 'url',
            'total_items': 2,
            'processed_items': 1,
            'created_at': _at(0),
          },
        ],
      },
      itemsByJobId: {
        'job-c': [
          {
            'id': 'item-stuck',
            'status': 'pending',
            'source_type': 'url',
            'created_at': _at(1),
          },
        ],
      },
    );
    _register(client);

    await tester.pumpWidget(_wrap(const ImportsTab()));
    // Not pumpAndSettle: the in-progress row's progress indicator animates
    // forever, so it never settles (same reason as the four-section test).
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('All clear — no imports yet'), findsNothing);
    expect(find.byType(ImportRow), findsOneWidget);
  });

  testWidgets('a batches outage costs only the batch rows (impvis1)',
      (tester) async {
    // Jobs and items are the main surface. A /v1/parser/batches failure
    // must degrade to "no pre-fan-out rows", not to an error screen —
    // the failure is reported, not swallowed.
    final client = _FakeApiClient(
      jobsByStatus: {
        'processing': [
          {
            'id': 'job-1',
            'status': 'processing',
            'source_type': 'url',
            'total_items': 1,
            'processed_items': 0,
            'created_at': _at(0),
          },
        ],
      },
    )..parserBatchesThrow = true;
    _register(client);

    await tester.pumpWidget(_wrap(const ImportsTab()));
    // Not pumpAndSettle: the in-progress row's progress indicator animates
    // forever, so it never settles (same reason as the four-section test).
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('Failed to load imports'), findsNothing);
    expect(find.byType(ImportRow), findsOneWidget);
  });

  testWidgets('yellow row taps navigate to review screen', (tester) async {
    final api = _FakeApiClient(
      jobsByStatus: {
        'awaiting_review': [
          {
            'id': 'job-r',
            'status': 'awaiting_review',
            'source_type': 'photo',
            'created_at': _at(10),
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
            'created_at': _at(15),
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
