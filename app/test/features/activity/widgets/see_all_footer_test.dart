import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
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

class _FakeApiClient extends ApiClient {
  final List<String> unarchiveCalls = [];
  final List<String> archiveCalls = [];
  bool unarchiveThrows = false;

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
    archiveCalls.add(id);
    return _fakeResponse({'id': id, 'archived_at': '2026-04-18T12:00:00Z'});
  }
}

void _register(_FakeApiClient client) {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  gi.registerSingleton<ApiClient>(client);
}

void _unregister() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
}

Widget _wrap(Widget child) => ProviderScope(
      child: MaterialApp(home: Scaffold(body: child)),
    );

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  tearDown(_unregister);

  testWidgets('count=0 renders nothing', (tester) async {
    _register(_FakeApiClient());
    await tester.pumpWidget(_wrap(
      SeeAllFooter(count: 0, onLoad: () async => const []),
    ));
    await tester.pumpAndSettle();

    expect(find.textContaining('See all'), findsNothing);
  });

  testWidgets('collapsed shows "See all (N)" and expand loads rows',
      (tester) async {
    _register(_FakeApiClient());
    var loaded = 0;
    await tester.pumpWidget(_wrap(
      SeeAllFooter(
        count: 3,
        onLoad: () async {
          loaded++;
          return [
            const SeeAllItemView(
              id: 'arc-1',
              title: 'Old archived',
              sourceType: 'url',
              statusLabel: 'completed',
              archivedAt: null,
              createdAt: null,
            ),
            const SeeAllItemView(
              id: 'arc-2',
              title: 'Older still',
              sourceType: 'url',
              statusLabel: 'failed',
              archivedAt: null,
              createdAt: null,
            ),
          ];
        },
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('See all (3)'), findsOneWidget);
    expect(find.text('Old archived'), findsNothing);

    await tester.tap(find.text('See all (3)'));
    await tester.pumpAndSettle();

    expect(find.text('Old archived'), findsOneWidget);
    expect(find.text('Older still'), findsOneWidget);
    expect(loaded, 1);
  });

  testWidgets('second expand does not refetch', (tester) async {
    _register(_FakeApiClient());
    var loaded = 0;
    await tester.pumpWidget(_wrap(
      SeeAllFooter(
        count: 1,
        onLoad: () async {
          loaded++;
          return [
            const SeeAllItemView(
              id: 'arc-1',
              title: 'Cached',
              sourceType: 'url',
              statusLabel: 'completed',
              archivedAt: null,
              createdAt: null,
            ),
          ];
        },
      ),
    ));
    await tester.pumpAndSettle();

    await tester.tap(find.text('See all (1)'));
    await tester.pumpAndSettle();
    expect(loaded, 1);

    // Collapse.
    await tester.tap(find.text('See all (1)'));
    await tester.pumpAndSettle();
    expect(find.text('Cached'), findsNothing);

    // Re-expand.
    await tester.tap(find.text('See all (1)'));
    await tester.pumpAndSettle();
    expect(loaded, 1, reason: 'onLoad cached from first expand');
    expect(find.text('Cached'), findsOneWidget);
  });

  testWidgets('swipe-right unarchives and fires API', (tester) async {
    final api = _FakeApiClient();
    _register(api);
    await tester.pumpWidget(_wrap(
      SeeAllFooter(
        count: 1,
        onLoad: () async => [
          const SeeAllItemView(
            id: 'arc-1',
            title: 'Unarchive me',
            sourceType: 'url',
            statusLabel: 'awaiting_review',
            archivedAt: null,
            createdAt: null,
          ),
        ],
      ),
    ));
    await tester.pumpAndSettle();
    await tester.tap(find.text('See all (1)'));
    await tester.pumpAndSettle();

    // Swipe-right (positive dx).
    await tester.drag(find.byType(Dismissible).first, const Offset(500, 0));
    await tester.pumpAndSettle();

    expect(api.unarchiveCalls, equals(['arc-1']));
    expect(find.text('Unarchived'), findsOneWidget);
    expect(find.text('Undo'), findsOneWidget);
  });
}
