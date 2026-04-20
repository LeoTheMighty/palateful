import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/activity/notifications_tab.dart';
import 'package:palateful/features/activity/providers/activity_read_provider.dart';

Response<dynamic> _fakeResponse(dynamic data, {int status = 200}) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: status,
    );

class _FakeApiClient extends ApiClient {
  final List<dynamic> activities;
  final List<String> markReadCalls = [];
  final List<String> archiveCalls = [];
  final List<String> unarchiveCalls = [];
  bool failArchive = false;

  _FakeApiClient({required this.activities});

  @override
  Future<Response> getActivities({int limit = 50, int offset = 0}) async =>
      _fakeResponse({'items': activities, 'total': activities.length});

  @override
  Future<Response> getActivitiesSeeAllCount() async =>
      _fakeResponse({'archived': 0, 'read_and_older': 0, 'total': 0});

  @override
  Future<Response> listActivitiesSeeAll({String? cursor, int limit = 50}) async =>
      _fakeResponse({'items': <dynamic>[], 'next_cursor': null, 'total': 0});

  @override
  Future<Response> markActivityRead(String id) async {
    markReadCalls.add(id);
    return _fakeResponse({'success': true});
  }

  @override
  Future<Response> markAllActivitiesRead() async =>
      _fakeResponse({'success': true});

  @override
  Future<Response> getUnreadActivityCount() async =>
      _fakeResponse({'count': 0});

  @override
  Future<Response> archiveActivity(String id) async {
    archiveCalls.add(id);
    if (failArchive) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/activities/$id/archive'),
        response: Response(
          requestOptions: RequestOptions(path: ''),
          statusCode: 500,
          statusMessage: 'server error',
        ),
      );
    }
    return _fakeResponse({'id': id, 'archived_at': '2026-04-18T12:00:00Z'});
  }

  @override
  Future<Response> unarchiveActivity(String id) async {
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

Future<void> _swipeFirstRow(WidgetTester tester) async {
  await tester.drag(find.byType(Dismissible).first, const Offset(-500, 0));
  await tester.pumpAndSettle();
}

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  tearDown(_unregister);

  testWidgets('renders non-import activities in chronological order',
      (tester) async {
    final api = _FakeApiClient(activities: [
      {
        'id': 'a-1',
        'type': 'partner_action',
        'title': 'Partner added a recipe',
        'read': true,
        'created_at': '2026-04-16T12:00:00Z',
      },
      {
        'id': 'imp-1',
        'type': 'import_failed',
        'title': 'Import failed (should not render)',
        'read': true,
        'created_at': '2026-04-16T12:05:00Z',
      },
      {
        'id': 'a-2',
        'type': 'invitation',
        'title': 'You were invited',
        'read': true,
        'created_at': '2026-04-16T12:10:00Z',
      },
    ]);
    _register(api);

    await tester.pumpWidget(_wrap(const NotificationsTab()));
    await tester.pumpAndSettle();

    expect(find.text('Partner added a recipe'), findsOneWidget);
    expect(find.text('You were invited'), findsOneWidget);
    expect(find.text('Import failed (should not render)'), findsNothing);
  });

  testWidgets('swipe archives optimistically and fires archive API',
      (tester) async {
    final api = _FakeApiClient(activities: [
      {
        'id': 'a-1',
        'type': 'partner_action',
        'title': 'Row to archive',
        'read': true,
        'created_at': '2026-04-16T12:00:00Z',
      },
      {
        'id': 'a-2',
        'type': 'invitation',
        'title': 'Stays',
        'read': true,
        'created_at': '2026-04-16T12:05:00Z',
      },
    ]);
    _register(api);

    await tester.pumpWidget(_wrap(const NotificationsTab()));
    await tester.pumpAndSettle();

    await _swipeFirstRow(tester);

    // Row is gone from the list.
    expect(find.text('Row to archive'), findsNothing);
    expect(find.text('Stays'), findsOneWidget);
    // API fired with the right id.
    expect(api.archiveCalls, equals(['a-1']));
    // 3s undo snackbar is present.
    expect(find.text('Archived'), findsOneWidget);
    expect(find.text('Undo'), findsOneWidget);
  });

  testWidgets('tapping Undo restores the row and fires unarchive',
      (tester) async {
    final api = _FakeApiClient(activities: [
      {
        'id': 'a-1',
        'type': 'partner_action',
        'title': 'Row to archive',
        'read': true,
        'created_at': '2026-04-16T12:00:00Z',
      },
    ]);
    _register(api);

    await tester.pumpWidget(_wrap(const NotificationsTab()));
    await tester.pumpAndSettle();

    await _swipeFirstRow(tester);
    await tester.tap(find.text('Undo'));
    await tester.pumpAndSettle();

    expect(find.text('Row to archive'), findsOneWidget);
    expect(api.unarchiveCalls, equals(['a-1']));
  });

  testWidgets('archive failure restores the row + shows error snackbar',
      (tester) async {
    final api = _FakeApiClient(activities: [
      {
        'id': 'a-1',
        'type': 'partner_action',
        'title': 'Row to archive',
        'read': true,
        'created_at': '2026-04-16T12:00:00Z',
      },
    ])
      ..failArchive = true;
    _register(api);

    await tester.pumpWidget(_wrap(const NotificationsTab()));
    await tester.pumpAndSettle();

    await _swipeFirstRow(tester);
    // Drain pending timers/microtasks to let the failure propagate. We
    // can't `pumpAndSettle` here because the error snackbar itself runs
    // a 3s timer — so pump once per frame until the error snackbar
    // surfaces (bounded).
    for (var i = 0; i < 10 && api.archiveCalls.isEmpty; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }
    await tester.pump(const Duration(milliseconds: 500));

    expect(api.archiveCalls, equals(['a-1']),
        reason: 'archive API is called even on failure');
    expect(find.text("Couldn't archive, try again"), findsOneWidget);
    expect(find.text('Row to archive'), findsOneWidget);
  });

  testWidgets('empty state shows "You\'re all caught up"', (tester) async {
    final api = _FakeApiClient(activities: []);
    _register(api);

    await tester.pumpWidget(_wrap(const NotificationsTab()));
    await tester.pumpAndSettle();

    expect(find.text("You're all caught up"), findsOneWidget);
  });
}
