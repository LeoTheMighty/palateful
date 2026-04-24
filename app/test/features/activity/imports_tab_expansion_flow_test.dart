import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/activity/imports_tab.dart';
import 'package:palateful/features/activity/providers/activity_read_provider.dart';

// irrd-7 integration test: yellow row → tap caret → expansion opens →
// tap Review → assert GoRouter navigated to /recipes/import/review/:id.

Response<dynamic> _fakeResponse(dynamic data, {int status = 200}) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: status,
    );

class _FakeApiClient extends ApiClient {
  final Map<String, List<dynamic>> jobsByStatus;
  final Map<String, List<dynamic>> itemsByJobId;
  int telemetryCalls = 0;

  _FakeApiClient({this.jobsByStatus = const {}, this.itemsByJobId = const {}});

  @override
  Future<Response> listImportJobs({
    String? status,
    int limit = 20,
    int offset = 0,
    bool includeArchived = false,
    bool archivedOnly = false,
    String? cursor,
  }) async {
    if (archivedOnly) return _fakeResponse({'jobs': []});
    if (status == null) {
      final all = <dynamic>[
        for (final entry in jobsByStatus.entries) ...entry.value,
      ];
      return _fakeResponse({'jobs': all});
    }
    return _fakeResponse({'jobs': jobsByStatus[status] ?? const []});
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
      for (final item in itemsByJobId[jobId] ?? const []) {
        out.add({...item as Map<String, dynamic>, 'job_id': jobId});
      }
    }
    return _fakeResponse({'items': out});
  }

  @override
  Future<Response> getImportItemTelemetry(String itemId) async {
    telemetryCalls++;
    return _fakeResponse({
      'stages': [
        {'stage': 'parsed', 'status': 'ok'},
        {
          'stage': 'extracted',
          'status': 'ok',
          'raw_output_preview': '{"title":"Pie","ingredients":[]}',
        },
        {'stage': 'matched', 'status': 'pending'},
        {'stage': 'created', 'status': 'pending'},
      ],
    });
  }
}

List<String> _navLog = [];

Widget _wrapWithRouter() {
  _navLog = [];
  final router = GoRouter(
    initialLocation: '/',
    routes: [
      GoRoute(
        path: '/',
        builder: (_, _) => const Scaffold(body: ImportsTab()),
      ),
      GoRoute(
        path: '/recipes/import/review/:itemId',
        builder: (_, state) {
          _navLog
              .add('/recipes/import/review/${state.pathParameters['itemId']}');
          return Scaffold(
            body: Text('REVIEW-${state.pathParameters['itemId']}'),
          );
        },
      ),
    ],
  );
  return ProviderScope(child: MaterialApp.router(routerConfig: router));
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

// Bounded pump loop — StageTimeline's pulse animation never settles.
Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 10; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  setUpAll(() async {
  });

  tearDown(_unregister);

  testWidgets(
      'yellow caret → expansion → tap Review → navigates to review screen',
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
            'recipe_name': 'Mom\'s Cake',
            'source_type': 'photo',
            'confidence_score': 0.62,
            'confidence_source': 'model',
            'awaiting_review_reason': 'low_confidence',
            'created_at': '2026-04-18T10:15:00Z',
          },
        ],
      },
    );
    _register(api);

    await tester.pumpWidget(_wrapWithRouter());
    await _settle(tester);

    // Row rendered with its inline confidence badge + reason chip.
    expect(find.text('Mom\'s Cake'), findsOneWidget);
    expect(find.text('62%'), findsOneWidget);
    expect(find.text('low confidence'), findsOneWidget);

    // Tap the row's caret via its IconButton tooltip (the caret is an
    // IconButton with a per-state tooltip label).
    await tester.tap(find.byTooltip("Show details for Mom's Cake"));
    await _settle(tester);

    // Expansion rendered: stage timeline + review button.
    expect(find.text('Parsed'), findsOneWidget);
    expect(find.text('Review'), findsOneWidget);
    expect(api.telemetryCalls, 1);

    // Tap Review → navigates.
    await tester.tap(find.text('Review'));
    await _settle(tester);

    expect(_navLog, ['/recipes/import/review/item-review']);
  });
}
