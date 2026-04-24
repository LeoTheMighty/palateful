import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/activity/widgets/notifications_see_all_footer.dart';

Response<dynamic> _fakeResponse(dynamic data, {int status = 200}) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: status,
    );

/// Builds a paginated-activity payload with `n` rows plus an optional
/// next cursor. Rows are deterministic for assertion.
Map<String, dynamic> _page(int n, {String prefix = 'row', String? next}) {
  return {
    'items': List.generate(n, (i) {
      return {
        'id': '$prefix-$i',
        'type': 'partner_action',
        'title': '$prefix title $i',
        'read': true,
        'created_at': '2026-01-01T00:00:00Z',
        'archived_at': '2026-02-01T00:00:00Z',
      };
    }),
    'next_cursor': next,
    'total': 0,
    'limit': 50,
    'offset': 0,
  };
}

class _FakeApiClient extends ApiClient {
  int countArchived;
  int countOther;
  bool countThrows = false;
  final List<String?> cursorsSeen = [];
  final List<Map<String, dynamic>> pagesToReturn;
  final List<String> unarchiveCalls = [];
  bool unarchiveThrows = false;
  bool failPage = false;

  _FakeApiClient({
    this.countArchived = 0,
    this.countOther = 0,
    required this.pagesToReturn,
  });

  @override
  Future<Response> getActivitiesSeeAllCount() async {
    if (countThrows) {
      throw DioException(requestOptions: RequestOptions(path: ''));
    }
    return _fakeResponse({
      'archived': countArchived,
      'read_and_older': countOther,
      'total': countArchived + countOther,
    });
  }

  @override
  Future<Response> listActivitiesSeeAll({String? cursor, int limit = 50}) async {
    cursorsSeen.add(cursor);
    if (failPage) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/activities'),
        response: Response(
          requestOptions: RequestOptions(path: ''),
          statusCode: 500,
        ),
      );
    }
    // Return the first queued page; subsequent calls pop in order.
    if (pagesToReturn.isEmpty) {
      return _fakeResponse(_page(0));
    }
    final page = pagesToReturn.removeAt(0);
    return _fakeResponse(page);
  }

  @override
  Future<Response> unarchiveActivity(String id) async {
    unarchiveCalls.add(id);
    if (unarchiveThrows) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/activities/$id/unarchive'),
        response: Response(
          requestOptions: RequestOptions(path: ''),
          statusCode: 500,
        ),
      );
    }
    return _fakeResponse({'id': id, 'archived_at': null});
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

/// Wraps the footer inside a `ListView` so the footer has an ancestor
/// Scrollable for its scroll-to-end trigger to attach to. Production
/// wiring lives on `NotificationsTab` — this harness mirrors the shape.
Widget _wrap(Widget child) => ProviderScope(
      child: MaterialApp(
        home: Scaffold(body: ListView(children: [child])),
      ),
    );

void main() {
  setUpAll(() async {
  });

  tearDown(_unregister);

  testWidgets('total == 0 renders SizedBox.shrink (no label, no caret)',
      (tester) async {
    _register(_FakeApiClient(pagesToReturn: const []));
    await tester.pumpWidget(_wrap(const NotificationsSeeAllFooter()));
    await tester.pumpAndSettle();
    expect(find.textContaining('See all'), findsNothing);
  });

  testWidgets('collapsed shows "See all (N)"; expanding loads page 1',
      (tester) async {
    final api = _FakeApiClient(
      countArchived: 12,
      countOther: 130,
      pagesToReturn: [
        _page(50, prefix: 'p1', next: 'CURSOR2'),
      ],
    );
    _register(api);

    await tester.pumpWidget(_wrap(const NotificationsSeeAllFooter()));
    await tester.pumpAndSettle();

    expect(find.text('See all (142)'), findsOneWidget);
    expect(find.text('p1 title 0'), findsNothing);

    await tester.tap(find.text('See all (142)'));
    await tester.pumpAndSettle();

    expect(find.text('p1 title 0'), findsOneWidget);
    expect(find.text('p1 title 49'), findsOneWidget);
    expect(api.cursorsSeen, [null]);
  });

  testWidgets('scrolling to the bottom fires the next-page fetch',
      (tester) async {
    final api = _FakeApiClient(
      countArchived: 100,
      countOther: 0,
      pagesToReturn: [
        _page(50, prefix: 'p1', next: 'CURSOR2'),
        _page(50, prefix: 'p2', next: null),
      ],
    );
    _register(api);

    await tester.pumpWidget(_wrap(const NotificationsSeeAllFooter()));
    await tester.pumpAndSettle();
    await tester.tap(find.text('See all (100)'));
    await tester.pumpAndSettle();

    // First page loaded.
    expect(find.text('p1 title 0'), findsOneWidget);

    // Scroll to the bottom to trigger the next-page load.
    await tester.drag(find.byType(ListView), const Offset(0, -4000));
    await tester.pumpAndSettle();

    expect(api.cursorsSeen, equals([null, 'CURSOR2']));
    expect(find.text("That's everything. (100 total)"), findsOneWidget);
  });

  testWidgets('page-fetch failure renders retry row; tap retries',
      (tester) async {
    final api = _FakeApiClient(
      countArchived: 60,
      countOther: 0,
      pagesToReturn: [_page(50, prefix: 'p1', next: 'CURSOR2')],
    );
    _register(api);

    await tester.pumpWidget(_wrap(const NotificationsSeeAllFooter()));
    await tester.pumpAndSettle();
    await tester.tap(find.text('See all (60)'));
    await tester.pumpAndSettle();

    // Set the next page to fail, then scroll to trigger it.
    api.failPage = true;
    await tester.drag(find.byType(ListView), const Offset(0, -4000));
    await tester.pumpAndSettle();

    expect(find.text("Couldn't load more. Tap to retry."), findsOneWidget);

    // Recover: queue a successful next page + clear the failure flag.
    api.failPage = false;
    api.pagesToReturn.add(_page(10, prefix: 'p2', next: null));
    // Scroll the retry row into view + settle before tapping (in a
    // test viewport 800x600, the retry row sits just below the
    // bottom — nudge the outer ListView further to expose it).
    await tester.scrollUntilVisible(
      find.text("Couldn't load more. Tap to retry."),
      100,
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text("Couldn't load more. Tap to retry."));
    await tester.pumpAndSettle();

    expect(find.text('p2 title 0'), findsOneWidget);
    expect(find.text("Couldn't load more. Tap to retry."), findsNothing);
  });

  testWidgets('swipe-right unarchives, shows Undo snackbar, fires API',
      (tester) async {
    final api = _FakeApiClient(
      countArchived: 1,
      countOther: 0,
      pagesToReturn: [_page(1, prefix: 'row', next: null)],
    );
    _register(api);

    await tester.pumpWidget(_wrap(const NotificationsSeeAllFooter()));
    await tester.pumpAndSettle();
    await tester.tap(find.text('See all (1)'));
    await tester.pumpAndSettle();

    // Swipe right (positive dx).
    await tester.drag(find.byType(Dismissible).first, const Offset(500, 0));
    await tester.pumpAndSettle();

    expect(api.unarchiveCalls, equals(['row-0']));
    expect(find.text('Unarchived'), findsOneWidget);
    expect(find.text('Undo'), findsOneWidget);
  });

  testWidgets('collapse + re-expand does NOT refetch page 1', (tester) async {
    final api = _FakeApiClient(
      countArchived: 1,
      countOther: 0,
      pagesToReturn: [_page(1, prefix: 'cached', next: null)],
    );
    _register(api);

    await tester.pumpWidget(_wrap(const NotificationsSeeAllFooter()));
    await tester.pumpAndSettle();

    await tester.tap(find.text('See all (1)'));
    await tester.pumpAndSettle();
    expect(find.text('cached title 0'), findsOneWidget);

    await tester.tap(find.text('See all (1)'));
    await tester.pumpAndSettle();
    expect(find.text('cached title 0'), findsNothing);

    await tester.tap(find.text('See all (1)'));
    await tester.pumpAndSettle();
    expect(find.text('cached title 0'), findsOneWidget);
    // API called exactly once for page 1 across the three toggles.
    expect(api.cursorsSeen, equals([null]));
  });
}
