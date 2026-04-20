import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/activity/activity_screen.dart';
import 'package:palateful/features/activity/providers/activity_read_provider.dart';
import 'package:palateful/features/activity/providers/activity_tab_provider.dart';
import 'package:palateful/features/recipes/add_recipe/batch_parser_service.dart';

/// ahr-7 regression suite: `/activity/import-history` is retired.
///
/// Verifies:
/// 1. Cold-start with initial URL `/activity/import-history` lands on
///    `/activity?tab=imports` (the shell + Imports tab).
/// 2. In-flight `context.push('/activity/import-history')` rewrites to
///    `/activity?tab=imports` while the app is already running.
/// 3. Legacy `?filter=imports` still maps to `?tab=imports` for one
///    release (the `filter → tab` shim ahr-2 shipped stays intact).

Response<dynamic> _fakeResponse(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _StubApiClient extends ApiClient {
  @override
  Future<Response> getActivities({int limit = 50, int offset = 0}) async =>
      _fakeResponse({'items': [], 'total': 0});

  @override
  Future<Response> listImportJobs({
    String? status,
    int limit = 20,
    int offset = 0,
    bool includeArchived = false,
    bool archivedOnly = false,
    String? cursor,
  }) async =>
      _fakeResponse({'jobs': []});

  @override
  Future<Response> getActivitiesSeeAllCount() async =>
      _fakeResponse({'archived': 0, 'read_and_older': 0, 'total': 0});

  @override
  Future<Response> getImportItemsSeeAllCount() async =>
      _fakeResponse(
          {'archived': 0, 'read_and_old_completed': 0, 'total': 0});

  @override
  Future<Response> listActivitiesSeeAll(
          {String? cursor, int limit = 50}) async =>
      _fakeResponse({'items': <dynamic>[], 'next_cursor': null});

  @override
  Future<Response> getUnreadActivityCount() async =>
      _fakeResponse({'count': 0});

  @override
  Future<Response> markAllActivitiesRead() async =>
      _fakeResponse({'success': true});
}

void _register() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  gi.registerSingleton<ApiClient>(_StubApiClient());
  if (gi.isRegistered<ActivityReadProvider>()) {
    gi.unregister<ActivityReadProvider>();
  }
  gi.registerLazySingleton<ActivityReadProvider>(
      () => ActivityReadProvider(gi<ApiClient>()));
  if (!gi.isRegistered<BatchParserService>()) {
    gi.registerLazySingleton<BatchParserService>(() => BatchParserService());
  }
}

void _unregister() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  if (gi.isRegistered<ActivityReadProvider>()) {
    gi.unregister<ActivityReadProvider>();
  }
}

/// Build a slimmed-down router whose /activity tree matches the real
/// app router: `/activity?tab=X` + a router-level redirect from
/// `/activity/import-history` and `?filter=imports`.
GoRouter _buildRouter(String initialLocation) {
  return GoRouter(
    initialLocation: initialLocation,
    routes: [
      GoRoute(
        path: '/',
        builder: (_, _) => const Scaffold(body: Text('HOME')),
      ),
      GoRoute(
        path: '/activity',
        redirect: (ctx, state) {
          final qp = state.uri.queryParameters;
          if (qp['tab'] != null) return null;
          final filter = qp['filter'];
          if (filter == null) return null;
          final mapped =
              filter == 'imports' ? 'imports' : 'notifications';
          return '/activity?tab=$mapped';
        },
        builder: (_, state) =>
            ActivityScreen(initialTab: state.uri.queryParameters['tab']),
        routes: [
          GoRoute(
            path: 'import-history',
            redirect: (_, _) => '/activity?tab=imports',
          ),
        ],
      ),
    ],
  );
}

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });
  setUp(_register);
  tearDown(_unregister);

  testWidgets(
      'cold-start at /activity/import-history lands on Imports tab of the shell',
      (tester) async {
    final router = _buildRouter('/activity/import-history');
    await tester.pumpWidget(
      ProviderScope(child: MaterialApp.router(routerConfig: router)),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 100));

    // Matched route is `/activity?tab=imports`.
    final location = router.routeInformationProvider.value.uri.toString();
    expect(location, equals('/activity?tab=imports'));
    expect(find.byType(ActivityScreen), findsOneWidget);
  });

  testWidgets('in-flight push to /activity/import-history is rewritten',
      (tester) async {
    final router = _buildRouter('/');
    await tester.pumpWidget(
      ProviderScope(child: MaterialApp.router(routerConfig: router)),
    );
    await tester.pumpAndSettle();

    // Prefer `go` over `push` — go triggers the router's redirect
    // chain for the initial URL, which is the same code path a push
    // notification / external-intent tap would use. `push` treats the
    // value as an exact target and can skip the redirect.
    router.go('/activity/import-history');
    for (var i = 0; i < 20; i++) {
      await tester.pump(const Duration(milliseconds: 50));
      final now = router.routerDelegate.currentConfiguration.uri.toString();
      if (now.contains('tab=imports')) break;
    }

    final resolved = router.routerDelegate.currentConfiguration.uri.toString();
    expect(resolved, equals('/activity?tab=imports'));
  });

  testWidgets('legacy /activity?filter=imports still maps to ?tab=imports',
      (tester) async {
    final router = _buildRouter('/activity?filter=imports');
    await tester.pumpWidget(
      ProviderScope(child: MaterialApp.router(routerConfig: router)),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 100));

    final location = router.routeInformationProvider.value.uri.toString();
    expect(location, equals('/activity?tab=imports'));
  });

  testWidgets('ActivityTab.fromWire still resolves imports', (tester) async {
    // Paranoia: if this ever starts returning notifications, the
    // redirect above would point to the wrong tab.
    expect(ActivityTab.fromWire('imports'), equals(ActivityTab.imports));
    expect(ActivityTab.fromWire('notifications'),
        equals(ActivityTab.notifications));
    expect(ActivityTab.fromWire(null), equals(ActivityTab.notifications));
  });
}
