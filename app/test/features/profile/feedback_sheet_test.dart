import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/profile/services/feedback_cache_service.dart';
import 'package:palateful/features/profile/widgets/feedback_sheet.dart';

class _FakeApiClient extends ApiClient {
  _FakeApiClient({this.throwOnSubmit = false, this.captureCalls});

  final bool throwOnSubmit;
  final List<Map<String, dynamic>>? captureCalls;

  @override
  Future<Response> submitFeedback({
    required String body,
    String? category,
    Map<String, dynamic>? context,
  }) async {
    captureCalls?.add({
      'body': body,
      'category': category,
      'context': context,
    });
    if (throwOnSubmit) {
      throw DioException(requestOptions: RequestOptions(path: ''));
    }
    return Response(
      requestOptions: RequestOptions(path: ''),
      statusCode: 201,
      data: {'id': 'feedback-1', 'status': 'submitted'},
    );
  }
}

void main() {
  setUpAll(() async {
    TestWidgetsFlutterBinding.ensureInitialized();
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  group('FeedbackCacheService', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({});
    });

    test('queueFeedback persists entries in FIFO order', () async {
      final cache = FeedbackCacheService();
      await cache.queueFeedback(body: 'first');
      await cache.queueFeedback(body: 'second', category: 'idea');

      final pending = await cache.getPendingFeedback();
      expect(pending, hasLength(2));
      expect(pending[0]['body'], equals('first'));
      expect(pending[1]['body'], equals('second'));
      expect(pending[1]['category'], equals('idea'));
    });

    test('clearPendingFeedback drops all entries', () async {
      final cache = FeedbackCacheService();
      await cache.queueFeedback(body: 'drop me');
      expect(await cache.hasPending(), isTrue);
      await cache.clearPendingFeedback();
      expect(await cache.hasPending(), isFalse);
    });

    test('hasPending returns false when nothing queued', () async {
      final cache = FeedbackCacheService();
      expect(await cache.hasPending(), isFalse);
    });
  });

  group('FeedbackSheet', () {
    late FeedbackCacheService cache;

    setUp(() {
      SharedPreferences.setMockInitialValues({});
      cache = FeedbackCacheService();
    });

    Widget buildSheet({
      required void Function(bool online) onComplete,
      ApiClient? apiClient,
      bool isOffline = false,
    }) {
      return MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (ctx) => FeedbackSheet(
              apiClient: apiClient,
              cache: cache,
              isOffline: isOffline,
              onComplete: onComplete,
              platform: 'ios',
              currentRoute: '/profile',
            ),
          ),
        ),
      );
    }

    testWidgets('Send disabled until body is non-empty', (tester) async {
      await tester.pumpWidget(buildSheet(onComplete: (_) {}));

      final sendFinder = find.byKey(const Key('feedback_send_button'));
      final button = tester.widget<FilledButton>(sendFinder);
      expect(button.onPressed, isNull);

      await tester.enterText(
        find.byKey(const Key('feedback_body_field')),
        'Hello',
      );
      await tester.pump();

      final enabled = tester.widget<FilledButton>(sendFinder);
      expect(enabled.onPressed, isNotNull);
    });

    testWidgets('Character counter turns red past 3900', (tester) async {
      await tester.pumpWidget(buildSheet(onComplete: (_) {}));

      await tester.enterText(
        find.byKey(const Key('feedback_body_field')),
        'a' * 3901,
      );
      await tester.pump();

      final counter = tester.widget<Text>(
        find.byKey(const Key('feedback_char_counter')),
      );
      expect(counter.data, equals('3901/4000'));
      expect(counter.style?.color, isNotNull);
    });

    testWidgets('Online submission calls submitFeedback and reports online',
        (tester) async {
      final calls = <Map<String, dynamic>>[];
      final fake = _FakeApiClient(captureCalls: calls);
      bool? completedOnline;

      await tester.pumpWidget(buildSheet(
        onComplete: (online) => completedOnline = online,
        apiClient: fake,
        isOffline: false,
      ));

      await tester.enterText(
        find.byKey(const Key('feedback_body_field')),
        'The share sheet bounces',
      );
      await tester.pump();
      await tester.tap(find.byKey(const Key('feedback_send_button')));
      await tester.pumpAndSettle();

      expect(completedOnline, isTrue);
      expect(calls, hasLength(1));
      expect(calls.first['body'], equals('The share sheet bounces'));
      expect(calls.first['context']['platform'], equals('ios'));
      expect(calls.first['context']['route'], equals('/profile'));

      // Queue stays empty on success
      expect(await cache.hasPending(), isFalse);
    });

    testWidgets('Offline submission queues and reports offline',
        (tester) async {
      bool? completedOnline;

      await tester.pumpWidget(buildSheet(
        onComplete: (online) => completedOnline = online,
        apiClient: null,
        isOffline: true,
      ));

      await tester.enterText(
        find.byKey(const Key('feedback_body_field')),
        "Couldn't reach the backend",
      );
      await tester.pump();
      await tester.tap(find.byKey(const Key('feedback_send_button')));
      await tester.pumpAndSettle();

      expect(completedOnline, isFalse);
      final pending = await cache.getPendingFeedback();
      expect(pending, hasLength(1));
      expect(pending.first['body'], equals("Couldn't reach the backend"));
    });

    testWidgets('Network error falls back to queue', (tester) async {
      final calls = <Map<String, dynamic>>[];
      final fake = _FakeApiClient(throwOnSubmit: true, captureCalls: calls);
      bool? completedOnline;

      await tester.pumpWidget(buildSheet(
        onComplete: (online) => completedOnline = online,
        apiClient: fake,
        isOffline: false,
      ));

      await tester.enterText(
        find.byKey(const Key('feedback_body_field')),
        'Hello',
      );
      await tester.pump();
      await tester.tap(find.byKey(const Key('feedback_send_button')));
      await tester.pumpAndSettle();

      expect(completedOnline, isFalse);
      expect(calls, hasLength(1));
      final pending = await cache.getPendingFeedback();
      expect(pending, hasLength(1));
      expect(pending.first['body'], equals('Hello'));
    });

    testWidgets('Category dropdown is forwarded in the payload',
        (tester) async {
      final calls = <Map<String, dynamic>>[];
      final fake = _FakeApiClient(captureCalls: calls);

      await tester.pumpWidget(buildSheet(
        onComplete: (_) {},
        apiClient: fake,
        isOffline: false,
      ));

      await tester.enterText(
        find.byKey(const Key('feedback_body_field')),
        'Ideas!',
      );
      await tester.pump();
      // Tap dropdown
      await tester.tap(find.byKey(const Key('feedback_category_dropdown')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Idea').last);
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('feedback_send_button')));
      await tester.pumpAndSettle();

      expect(calls, hasLength(1));
      expect(calls.first['category'], equals('idea'));
    });
  });
}
