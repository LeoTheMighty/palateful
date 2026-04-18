import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/activity/activity_screen.dart';
import 'package:palateful/features/activity/providers/activity_read_provider.dart';
import 'package:palateful/features/recipes/add_recipe/batch_parser_service.dart';

Response<dynamic> _fakeResponse(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _FakeApiClient extends ApiClient {
  final List<dynamic> activities;
  final List<String> markReadCalls = [];
  int markAllCalls = 0;
  int unreadCountCalls = 0;
  final List<String> archiveActivityCalls = [];
  final List<String> unarchiveActivityCalls = [];

  _FakeApiClient({required this.activities});

  @override
  Future<Response> getActivities({int limit = 50, int offset = 0}) async =>
      _fakeResponse({'items': activities, 'total': activities.length});

  @override
  Future<Response> listImportJobs(
          {String? status, int limit = 20, int offset = 0}) async =>
      _fakeResponse({'jobs': []});

  @override
  Future<Response> markActivityRead(String id) async {
    markReadCalls.add(id);
    return _fakeResponse({'success': true});
  }

  @override
  Future<Response> markAllActivitiesRead() async {
    markAllCalls++;
    return _fakeResponse({'success': true});
  }

  @override
  Future<Response> getUnreadActivityCount() async {
    unreadCountCalls++;
    return _fakeResponse({'count': 0});
  }

  @override
  Future<Response> archiveActivity(String id) async {
    archiveActivityCalls.add(id);
    return _fakeResponse({'id': id, 'archived_at': '2026-04-18T12:00:00Z'});
  }

  @override
  Future<Response> unarchiveActivity(String id) async {
    unarchiveActivityCalls.add(id);
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
  // Leave BatchParserService registered — shared with import_history tests
  // within the same test file batch.
}

Widget _wrap(Widget child) =>
    ProviderScope(child: MaterialApp(home: child));

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  tearDown(_unregister);

  testWidgets('on tab open, every loaded unread activity is marked read',
      (tester) async {
    final api = _FakeApiClient(
      activities: [
        {
          'id': 'a-1',
          'type': 'partner_action',
          'title': 'Partner added a recipe',
          'read': false,
          'created_at': '2026-04-16T12:00:00Z',
        },
        {
          'id': 'a-2',
          'type': 'invitation',
          'title': 'You were invited',
          'read': false,
          'created_at': '2026-04-16T12:05:00Z',
        },
        {
          'id': 'a-3',
          'type': 'meal_reminder',
          'title': 'Already acknowledged',
          'read': true,
          'created_at': '2026-04-16T11:00:00Z',
        },
      ],
    );
    _register(api);

    await tester.pumpWidget(_wrap(const ActivityScreen()));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    await tester.pump(const Duration(milliseconds: 50));

    // Every unread loaded item is marked — already-read rows are skipped.
    expect(api.markReadCalls..sort(), equals(['a-1', 'a-2']));
    expect(api.markAllCalls, 0,
        reason: 'Mark-all is the safety-valve, not the default flow');

    // Import-typed rows are out of scope for this surface — none in fixture.
  });

  testWidgets('import-typed activities in the feed are NOT marked by this tab',
      (tester) async {
    final api = _FakeApiClient(
      activities: [
        {
          'id': 'imp-1',
          'type': 'import_failed',
          'title': 'Import failed',
          'read': false,
          'created_at': '2026-04-16T12:00:00Z',
        },
        {
          'id': 'p-1',
          'type': 'partner_action',
          'title': 'Partner did a thing',
          'read': false,
          'created_at': '2026-04-16T12:05:00Z',
        },
      ],
    );
    _register(api);

    await tester.pumpWidget(_wrap(const ActivityScreen()));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(api.markReadCalls, equals(['p-1']),
        reason:
            'import_* activities belong to the Import Activity surface and '
            'must be acknowledged there, not here');
  });

  testWidgets(
      'renders a two-tab shell with Notifications default + Imports second',
      (tester) async {
    final api = _FakeApiClient(activities: []);
    _register(api);

    await tester.pumpWidget(_wrap(const ActivityScreen()));
    await tester.pump();

    expect(find.text('Notifications'), findsOneWidget);
    expect(find.text('Imports'), findsOneWidget);
    expect(find.byType(TabBar), findsOneWidget);
  });

  testWidgets('initialTab=imports preselects the Imports tab', (tester) async {
    final api = _FakeApiClient(activities: []);
    _register(api);

    await tester.pumpWidget(
      _wrap(const ActivityScreen(initialTab: 'imports')),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    // The TabController's animation completes in a couple of frames.
    await tester.pumpAndSettle(const Duration(milliseconds: 400));

    final tabBar = tester.widget<TabBar>(find.byType(TabBar));
    expect(tabBar.controller?.index, equals(1));
  });

  testWidgets('no-op when every loaded activity is already read',
      (tester) async {
    final api = _FakeApiClient(
      activities: [
        {
          'id': 'a-1',
          'type': 'partner_action',
          'title': 'already read',
          'read': true,
          'created_at': '2026-04-16T12:00:00Z',
        },
      ],
    );
    _register(api);

    await tester.pumpWidget(_wrap(const ActivityScreen()));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(api.markReadCalls, isEmpty);
  });
}
