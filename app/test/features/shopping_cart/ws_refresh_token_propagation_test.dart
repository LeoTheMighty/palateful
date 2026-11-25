import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/core/services/error_reporter.dart';
import 'package:palateful/features/shopping_cart/services/shopping_cart_service.dart';

/// btri01 — regression tests for the bas-3 WebSocket "refresh once on a
/// 4xxx close code" path (`e781a56`).
///
/// bas-3's AC5 assumed that after `AuthService.refreshToken()` succeeds,
/// "the next `_doConnect` uses the fresh token (pulled from
/// `_apiClient.authToken` as before)". That premise was false:
/// `refreshToken()` only rotates AuthService's own credentials, and the
/// single runtime writer of `ApiClient._authToken` is the Dio 401
/// interceptor (bas-4), which needs an HTTP 401 to fire. A WS-only
/// rejection never produces one, so every reconnect re-sent the same
/// rejected token — a permanent 5s reconnect + `ErrorReporter.report`
/// loop, which is what the legacy BUGS.md report "still seeing the
/// Websocket errors in crashlytics" describes.
///
/// These tests pin the token hand-off so the loop can't come back.

class _FakeAuthService extends AuthService {
  _FakeAuthService({
    this.refreshResult = true,
    this.refreshThrows = false,
  }) : _token = staleToken;

  static const staleToken = 'stale-ws-token';
  static const tokenAfterRefresh = 'refreshed-ws-token';

  final bool refreshResult;
  final bool refreshThrows;

  String? _token;
  int refreshCalls = 0;

  @override
  String? get accessToken => _token;

  @override
  Future<bool> refreshToken() async {
    refreshCalls++;
    if (refreshThrows) {
      throw StateError('renewCredentials blew up');
    }
    if (refreshResult) {
      _token = tokenAfterRefresh;
    }
    return refreshResult;
  }
}

class _CapturedReport {
  _CapturedReport(this.error, this.area, this.operation, this.extras);

  final Object error;
  final String? area;
  final String? operation;
  final Map<String, Object?>? extras;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late ApiClient api;
  late _FakeAuthService auth;
  late ShoppingCartService service;
  late List<_CapturedReport> reports;

  void register(_FakeAuthService fakeAuth) {
    final gi = GetIt.instance;
    if (gi.isRegistered<ShoppingCartService>()) {
      gi.unregister<ShoppingCartService>();
    }
    if (gi.isRegistered<AuthService>()) gi.unregister<AuthService>();
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();

    api = ApiClient();
    api.setAuthToken(_FakeAuthService.staleToken);
    auth = fakeAuth;
    gi.registerSingleton<ApiClient>(api);
    gi.registerSingleton<AuthService>(auth);
    gi.registerLazySingleton<ShoppingCartService>(() => ShoppingCartService());
    service = gi<ShoppingCartService>();
    service.setCurrentListIdForTest('list-1');
  }

  setUp(() {
    reports = [];
    ErrorReporter.testReportHook = (
      error,
      stack, {
      area,
      operation,
      extras,
      fatal = false,
    }) {
      reports.add(_CapturedReport(error, area, operation, extras));
    };
  });

  tearDown(() {
    ErrorReporter.testReportHook = null;
    // Cancels the 5s reconnect timer _refreshTokenThenReconnect schedules.
    service.disconnectWebSocket();
    final gi = GetIt.instance;
    if (gi.isRegistered<ShoppingCartService>()) {
      gi.unregister<ShoppingCartService>();
    }
    if (gi.isRegistered<AuthService>()) gi.unregister<AuthService>();
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  });

  group('bas-3 — WS 4xxx close → refresh once before reconnect', () {
    test('successful refresh hands the fresh token to ApiClient', () async {
      register(_FakeAuthService(refreshResult: true));

      await service.refreshTokenThenReconnectForTest(4003);

      expect(auth.refreshCalls, 1);
      expect(
        api.authToken,
        _FakeAuthService.tokenAfterRefresh,
        reason:
            'the reconnect reads _apiClient.authToken; leaving the rejected '
            'token there makes the 4003 close repeat forever',
      );
    });

    test('failed refresh leaves the existing token untouched', () async {
      register(_FakeAuthService(refreshResult: false));

      await service.refreshTokenThenReconnectForTest(4003);

      expect(auth.refreshCalls, 1);
      expect(
        api.authToken,
        _FakeAuthService.staleToken,
        reason: 'a refresh that returned false has no new token to install',
      );
    });

    test('throwing refresh is reported and does not clear the token',
        () async {
      register(_FakeAuthService(refreshThrows: true));

      await service.refreshTokenThenReconnectForTest(4003);

      expect(auth.refreshCalls, 1);
      expect(api.authToken, _FakeAuthService.staleToken);
      expect(
        reports.any((r) =>
            r.area == 'shopping.websocket' &&
            r.operation == 'refresh_on_disconnect'),
        isTrue,
        reason: 'a refresh that throws must reach audit_errors, not debugPrint',
      );
    });

    test('the close itself is reported with area, list id and close code',
        () async {
      register(_FakeAuthService(refreshResult: true));

      await service.refreshTokenThenReconnectForTest(4004);

      final disconnect = reports.firstWhere((r) => r.operation == 'disconnect');
      expect(disconnect.area, 'shopping.websocket');
      expect(disconnect.extras?['list_id'], 'list-1');
      expect(disconnect.extras?['close_code'], 4004);
    });
  });
}
