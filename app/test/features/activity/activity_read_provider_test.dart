import 'package:dio/dio.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/activity/providers/activity_read_provider.dart';

Response<dynamic> _fakeResponse(dynamic data, {int status = 200}) {
  return Response(
    data: data,
    requestOptions: RequestOptions(path: ''),
    statusCode: status,
  );
}

class _FakeApiClient extends ApiClient {
  final List<String> markedIds = [];
  final Map<String, int> attemptsPerId = {};
  final Set<String> failOnceIds;
  final Set<String> always404Ids;
  int unreadCountCalls = 0;
  int unreadCountValue;
  List<Map<String, dynamic>> activities;

  _FakeApiClient({
    this.failOnceIds = const {},
    this.always404Ids = const {},
    this.unreadCountValue = 0,
    this.activities = const [],
  });

  @override
  Future<Response> markActivityRead(String id) async {
    final prev = attemptsPerId[id] ?? 0;
    final attempt = prev + 1;
    attemptsPerId[id] = attempt;

    if (always404Ids.contains(id)) {
      throw DioException(
        requestOptions: RequestOptions(path: ''),
        response: Response(
          requestOptions: RequestOptions(path: ''),
          statusCode: 404,
        ),
      );
    }
    if (failOnceIds.contains(id) && attempt == 1) {
      throw DioException(
        requestOptions: RequestOptions(path: ''),
        type: DioExceptionType.connectionError,
      );
    }
    markedIds.add(id);
    return _fakeResponse({'success': true});
  }

  @override
  Future<Response> getUnreadActivityCount() async {
    unreadCountCalls++;
    return _fakeResponse({'count': unreadCountValue});
  }

  @override
  Future<Response> getActivities({int limit = 50, int offset = 0}) async {
    return _fakeResponse({'items': activities, 'total': activities.length});
  }
}

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  group('ActivityReadProvider', () {
    test('markIdsRead fires one request per id', () async {
      final api = _FakeApiClient();
      final provider = ActivityReadProvider(api);

      await provider.markIdsRead(['a', 'b', 'c']);

      expect(api.markedIds..sort(), equals(['a', 'b', 'c']));
      expect(api.attemptsPerId['a'], 1);
      expect(api.attemptsPerId['b'], 1);
      expect(api.attemptsPerId['c'], 1);
    });

    test('markIdsRead retries on transient failure (connection error)',
        () async {
      final api = _FakeApiClient(failOnceIds: {'flaky'});
      final provider = ActivityReadProvider(api);

      await provider.markIdsRead(['flaky']);

      expect(api.markedIds, contains('flaky'));
      expect(api.attemptsPerId['flaky'], 2,
          reason: 'should retry once after first failure');
    });

    test('markIdsRead does NOT retry on 4xx (activity gone)', () async {
      final api = _FakeApiClient(always404Ids: {'gone'});
      final provider = ActivityReadProvider(api);

      await provider.markIdsRead(['gone']);

      expect(api.attemptsPerId['gone'], 1,
          reason: '404 is terminal — do not spin on a deleted activity');
      expect(api.markedIds, isEmpty);
    });

    test('markIdsRead is a no-op on empty iterable', () async {
      final api = _FakeApiClient();
      final provider = ActivityReadProvider(api);

      await provider.markIdsRead(const []);

      expect(api.attemptsPerId, isEmpty);
    });

    test('refreshUnreadCount updates ValueNotifier', () async {
      final api = _FakeApiClient(unreadCountValue: 7);
      final provider = ActivityReadProvider(api);

      expect(provider.unreadCount.value, 0);
      await provider.refreshUnreadCount();
      expect(provider.unreadCount.value, 7);
      expect(api.unreadCountCalls, 1);
    });

    test('markLoadedImportActivitiesRead only touches import-typed unread',
        () async {
      final api = _FakeApiClient(
        activities: [
          {'id': '1', 'type': 'partner_action', 'read': false},
          {'id': '2', 'type': 'import_failed', 'read': false},
          {'id': '3', 'type': 'import_complete', 'read': true},
          {'id': '4', 'type': 'import_needs_review', 'read': false},
        ],
      );
      final provider = ActivityReadProvider(api);

      await provider.markLoadedImportActivitiesRead();

      expect(api.markedIds..sort(), equals(['2', '4']),
          reason: 'non-import and already-read activities are skipped');
    });

    test('setUnreadCount notifies listeners only on change', () async {
      final api = _FakeApiClient();
      final provider = ActivityReadProvider(api);
      var notifyCount = 0;
      provider.unreadCount.addListener(() => notifyCount++);

      provider.setUnreadCount(0);
      expect(notifyCount, 0, reason: 'same value = no notify');

      provider.setUnreadCount(3);
      expect(notifyCount, 1);

      provider.setUnreadCount(3);
      expect(notifyCount, 1, reason: 'stable value = no notify');
    });
  });
}
