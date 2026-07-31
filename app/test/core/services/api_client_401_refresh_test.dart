import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/auth_service.dart';

/// btri01 — regression tests for the bas-4 401-refresh interceptor
/// (`db1a8e4`, "Dio interceptor logs out on refresh failure").
///
/// The bas-4 story listed three unit tests in its acceptance criteria
/// (refresh-returns-false → logout, refresh-throws → logout,
/// refresh-succeeds → no logout) but shipped without them. These pin
/// the behavior so the legacy BUGS.md report "when token needs a
/// refresh sometimes get very strange errors in the app" can be closed
/// against something executable rather than a code read.
///
/// The real `Dio` is driven by an in-memory adapter so we can count
/// upstream round-trips and inspect the Authorization header the retry
/// actually sent.

/// Serves a scripted sequence of status codes, one per upstream fetch.
class _ScriptedAdapter implements HttpClientAdapter {
  _ScriptedAdapter(this.statuses);

  final List<int> statuses;
  final List<String?> sentAuthHeaders = [];
  int fetchCount = 0;

  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    sentAuthHeaders.add(options.headers['Authorization'] as String?);
    final status = fetchCount < statuses.length
        ? statuses[fetchCount]
        : statuses.last;
    fetchCount++;
    return ResponseBody.fromString(
      '{"hit":$fetchCount}',
      status,
      headers: {
        Headers.contentTypeHeader: ['application/json'],
      },
    );
  }
}

/// Stands in for the Auth0-backed AuthService. Only the two members the
/// interceptor touches (`refreshToken`, `logout`) plus `accessToken`
/// are overridden; the superclass constructor still runs, which is
/// fine — `Auth0` is only a value holder until a method is called.
class _FakeAuthService extends AuthService {
  _FakeAuthService({
    this.refreshResult = true,
    this.refreshThrows = false,
  }) : _token = 'stale-token';

  static const tokenAfterRefresh = 'refreshed-token';

  final bool refreshResult;
  final bool refreshThrows;

  String? _token;
  int refreshCalls = 0;
  int logoutCalls = 0;

  @override
  String? get accessToken => _token;

  @override
  Future<bool> refreshToken() async {
    refreshCalls++;
    if (refreshThrows) {
      throw StateError('refresh blew up');
    }
    if (refreshResult) {
      _token = tokenAfterRefresh;
    }
    return refreshResult;
  }

  @override
  Future<void> logout() async {
    logoutCalls++;
    _token = null;
  }
}

ApiClient _makeClient(_ScriptedAdapter adapter, _FakeAuthService auth) {
  final client = ApiClient();
  client.dio.httpClientAdapter = adapter;
  client.setAuthService(auth);
  client.setAuthToken('stale-token');
  return client;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('bas-4 — 401 refresh interceptor', () {
    test('refresh succeeds: request is retried with the new token, no logout',
        () async {
      final adapter = _ScriptedAdapter([401, 200]);
      final auth = _FakeAuthService(refreshResult: true);
      final client = _makeClient(adapter, auth);

      final response = await client.dio.get('/v1/users/me');

      expect(response.statusCode, 200);
      expect(auth.refreshCalls, 1);
      expect(auth.logoutCalls, 0, reason: 'a successful refresh must not log out');
      expect(adapter.fetchCount, 2, reason: 'original + one retry');
      expect(adapter.sentAuthHeaders.first, 'Bearer stale-token');
      expect(
        adapter.sentAuthHeaders.last,
        'Bearer refreshed-token',
        reason: 'the retry must carry the freshly refreshed token',
      );
    });

    test('refresh returns false: logs out instead of surfacing a mystery error',
        () async {
      final adapter = _ScriptedAdapter([401]);
      final auth = _FakeAuthService(refreshResult: false);
      final client = _makeClient(adapter, auth);

      await expectLater(
        client.dio.get('/v1/users/me'),
        throwsA(isA<DioException>()),
      );

      expect(auth.refreshCalls, 1);
      expect(auth.logoutCalls, 1,
          reason: 'refresh unavailable/rejected must kick the user to /login');
      expect(adapter.fetchCount, 1, reason: 'no retry when refresh failed');
    });

    test('refresh throws: still logs out', () async {
      final adapter = _ScriptedAdapter([401]);
      final auth = _FakeAuthService(refreshThrows: true);
      final client = _makeClient(adapter, auth);

      await expectLater(
        client.dio.get('/v1/users/me'),
        throwsA(isA<DioException>()),
      );

      expect(auth.refreshCalls, 1);
      expect(auth.logoutCalls, 1);
      expect(adapter.fetchCount, 1);
    });

    test('retry also 401: falls through without re-entering the refresh branch',
        () async {
      final adapter = _ScriptedAdapter([401, 401]);
      final auth = _FakeAuthService(refreshResult: true);
      final client = _makeClient(adapter, auth);

      await expectLater(
        client.dio.get('/v1/users/me'),
        throwsA(isA<DioException>()),
      );

      expect(auth.refreshCalls, 1, reason: 'the _isRefreshing guard holds');
      expect(adapter.fetchCount, 2, reason: 'exactly one retry, then give up');
    });

    test('no auth service wired: 401 propagates untouched', () async {
      final adapter = _ScriptedAdapter([401]);
      final client = ApiClient();
      client.dio.httpClientAdapter = adapter;
      client.setAuthToken('stale-token');

      await expectLater(
        client.dio.get('/v1/users/me'),
        throwsA(isA<DioException>()),
      );
      expect(adapter.fetchCount, 1);
    });
  });
}
