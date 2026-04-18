import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';

import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/admin/admin_feedback_screen.dart';

class _FakeApiClient extends ApiClient {
  _FakeApiClient({
    required this.listResponse,
    this.updateThrows = false,
    List<Map<String, dynamic>>? updateCalls,
  }) : updateCalls = updateCalls ?? <Map<String, dynamic>>[];

  final Map<String, dynamic> listResponse;
  final bool updateThrows;
  final List<Map<String, dynamic>> updateCalls;
  int listCalls = 0;
  final List<String> listStatusArgs = [];

  @override
  Future<Response> getAdminFeedback({
    String status = 'unread',
    int offset = 0,
    int limit = 25,
  }) async {
    listCalls++;
    listStatusArgs.add(status);
    return Response(
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
      data: listResponse,
    );
  }

  @override
  Future<Response> updateFeedbackStatus(String feedbackId, String status) async {
    updateCalls.add({'id': feedbackId, 'status': status});
    if (updateThrows) {
      throw DioException(requestOptions: RequestOptions(path: ''));
    }
    return Response(
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
      data: {
        'id': feedbackId,
        'status': status,
        'updated_at': DateTime.now().toIso8601String(),
      },
    );
  }
}

Map<String, dynamic> _feedback({
  String id = 'fb-1',
  String status = 'unread',
  String body = 'Share sheet bounces me to home',
  String? category,
  String? displayName = 'Jane Doe',
  String? email = 'jane@example.com',
  Map<String, dynamic>? context,
}) {
  return {
    'id': id,
    'user_id': 'u-1',
    'user_display_name': displayName,
    'user_email': email,
    'body': body,
    'category': category,
    'status': status,
    'context': context ??
        {'app_version': '1.0.13', 'platform': 'ios', 'route': '/profile'},
    'created_at': DateTime.now().toIso8601String(),
    'updated_at': DateTime.now().toIso8601String(),
  };
}

void main() {
  setUpAll(() async {
    TestWidgetsFlutterBinding.ensureInitialized();
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  setUp(() {
    if (GetIt.I.isRegistered<ApiClient>()) {
      GetIt.I.unregister<ApiClient>();
    }
  });

  Widget wrap(Widget child) => MaterialApp(home: child);

  testWidgets('loads with default unread filter and renders items',
      (tester) async {
    final fake = _FakeApiClient(
      listResponse: {
        'items': [_feedback()],
        'total': 1,
        'status': 'unread',
        'offset': 0,
        'limit': 25,
      },
    );
    GetIt.I.registerSingleton<ApiClient>(fake);

    await tester.pumpWidget(wrap(const AdminFeedbackScreen()));
    await tester.pumpAndSettle();

    expect(fake.listStatusArgs.first, equals('unread'));
    expect(find.text('Jane Doe'), findsOneWidget);
    expect(find.textContaining('Share sheet bounces'), findsOneWidget);
  });

  testWidgets('switching to Read filter re-queries', (tester) async {
    final fake = _FakeApiClient(
      listResponse: {
        'items': <Map<String, dynamic>>[],
        'total': 0,
        'status': 'read',
        'offset': 0,
        'limit': 25,
      },
    );
    GetIt.I.registerSingleton<ApiClient>(fake);

    await tester.pumpWidget(wrap(const AdminFeedbackScreen()));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('feedback_filter_read')));
    await tester.pumpAndSettle();

    expect(fake.listCalls, greaterThanOrEqualTo(2));
    expect(fake.listStatusArgs.last, equals('read'));
  });

  testWidgets('empty state shows the friendly message', (tester) async {
    final fake = _FakeApiClient(
      listResponse: {
        'items': <Map<String, dynamic>>[],
        'total': 0,
        'status': 'unread',
        'offset': 0,
        'limit': 25,
      },
    );
    GetIt.I.registerSingleton<ApiClient>(fake);

    await tester.pumpWidget(wrap(const AdminFeedbackScreen()));
    await tester.pumpAndSettle();

    expect(find.text('No feedback in this filter yet.'), findsOneWidget);
  });

  testWidgets('tap row opens detail drawer', (tester) async {
    final fake = _FakeApiClient(
      listResponse: {
        'items': [_feedback(id: 'fb-xyz')],
        'total': 1,
        'status': 'unread',
        'offset': 0,
        'limit': 25,
      },
    );
    GetIt.I.registerSingleton<ApiClient>(fake);

    await tester.pumpWidget(wrap(const AdminFeedbackScreen()));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('feedback_item_fb-xyz')));
    await tester.pumpAndSettle();

    // Full body + Mark Read + Archive visible in drawer
    expect(find.byKey(const Key('feedback_mark_read_button')), findsOneWidget);
    expect(find.byKey(const Key('feedback_archive_button')), findsOneWidget);
    expect(find.text('jane@example.com'), findsOneWidget);
  });

  testWidgets('Mark Read applies optimistically — row disappears under unread filter',
      (tester) async {
    final calls = <Map<String, dynamic>>[];
    final fake = _FakeApiClient(
      listResponse: {
        'items': [_feedback(id: 'fb-opt')],
        'total': 1,
        'status': 'unread',
        'offset': 0,
        'limit': 25,
      },
      updateCalls: calls,
    );
    GetIt.I.registerSingleton<ApiClient>(fake);

    await tester.pumpWidget(wrap(const AdminFeedbackScreen()));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('feedback_item_fb-opt')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('feedback_mark_read_button')));
    await tester.pumpAndSettle();

    expect(calls, hasLength(1));
    expect(calls.first['id'], equals('fb-opt'));
    expect(calls.first['status'], equals('read'));

    // Row flipped to read → hidden from unread filter
    expect(find.byKey(const Key('feedback_item_fb-opt')), findsNothing);
    expect(find.text('No feedback in this filter yet.'), findsOneWidget);
  });

  testWidgets('Mark Read failure rolls back and shows snackbar',
      (tester) async {
    final fake = _FakeApiClient(
      listResponse: {
        'items': [_feedback(id: 'fb-rb')],
        'total': 1,
        'status': 'unread',
        'offset': 0,
        'limit': 25,
      },
      updateThrows: true,
    );
    GetIt.I.registerSingleton<ApiClient>(fake);

    await tester.pumpWidget(wrap(const AdminFeedbackScreen()));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('feedback_item_fb-rb')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('feedback_mark_read_button')));
    await tester.pumpAndSettle();

    // Row reappears (rolled back) + snackbar visible
    expect(find.byKey(const Key('feedback_item_fb-rb')), findsOneWidget);
    expect(find.text("Couldn't update — tap to retry"), findsOneWidget);
  });

  testWidgets('initialStatus arg from router honoured', (tester) async {
    final fake = _FakeApiClient(
      listResponse: {
        'items': <Map<String, dynamic>>[],
        'total': 0,
        'status': 'archived',
        'offset': 0,
        'limit': 25,
      },
    );
    GetIt.I.registerSingleton<ApiClient>(fake);

    await tester.pumpWidget(
      wrap(const AdminFeedbackScreen(initialStatus: 'archived')),
    );
    await tester.pumpAndSettle();

    expect(fake.listStatusArgs.first, equals('archived'));
  });
}
