import 'dart:async';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/services.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/error_reporter.dart';
import 'package:palateful/core/services/push_notification_service.dart';

// push-diag-1 unit tests. The iOS-only service path is exercised via a
// fake PushMessagingClient + subclassed ApiClient. Tests capture
// ErrorReporter.report calls via the test hook and assert on the
// (area, operation, extras, error) tuple.

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  // ApiClient reads API_BASE_URL from dotenv at construction — stub it so
  // the subclassed FakeApiClient can run through super() without blowing
  // up on NotInitializedError in tests.
  dotenv.loadFromString(
    envString: 'API_BASE_URL=http://localhost\n',
    isOptional: true,
  );

  final capturedReports = <_ReportCall>[];
  final capturedLogs = <String>[];

  setUp(() {
    capturedReports.clear();
    capturedLogs.clear();
    ErrorReporter.testReportHook = (
      error,
      stack, {
      String? area,
      String? operation,
      Map<String, Object?>? extras,
      bool fatal = false,
    }) {
      capturedReports.add(_ReportCall(
        error: error,
        area: area,
        operation: operation,
        extras: extras,
        fatal: fatal,
      ));
    };
    ErrorReporter.testLogHook = capturedLogs.add;
  });

  tearDown(() {
    ErrorReporter.testReportHook = null;
    ErrorReporter.testLogHook = null;
  });

  group('PushNotificationService — ErrorReporter integration', () {
    test('A — requestPermission throws → reports ensureRegistered.outer',
        () async {
      if (!Platform.isIOS && !Platform.isMacOS) {
        // Flutter tests run on the dev machine (macOS). The service's
        // isAvailable gate is (iOS || Android) — on macOS it returns
        // early. Construct the fake so the isAvailable branch is taken;
        // macOS will short-circuit ensureRegistered → notDetermined with
        // no report. To get coverage in CI, we short-circuit this
        // platform check by exercising the logic path directly via a
        // subclassed service that forces isAvailable=true. See below.
      }

      final fakeMessaging = _FakePushMessagingClient(
        settings: _settings(AuthorizationStatus.notDetermined),
        requestPermissionBehavior: _Throw(StateError('prompt failed')),
      );
      final service = _TestablePushNotificationService(
        _FakeApiClient(),
        messagingClient: fakeMessaging,
      );

      final result = await service.ensureRegistered();

      expect(result, AuthorizationStatus.notDetermined);
      final report = capturedReports.singleWhere(
        (r) => r.operation == 'ensureRegistered.outer',
        orElse: () => fail(
            'Expected ensureRegistered.outer report, got: $capturedReports'),
      );
      expect(report.area, 'push');
      expect(report.error, isA<StateError>());
      expect(report.extras, isNotNull);
      expect(report.extras!.containsKey('platform'), isTrue);
    });

    test('B — granted + getToken null → reports getToken.nullAfterGranted',
        () async {
      final fakeMessaging = _FakePushMessagingClient(
        settings: _settings(AuthorizationStatus.authorized),
        tokenBehavior: _ReturnNull(),
      );
      final service = _TestablePushNotificationService(
        _FakeApiClient(),
        messagingClient: fakeMessaging,
      );

      await service.ensureRegistered();

      final report = capturedReports.singleWhere(
        (r) => r.operation == 'getToken.nullAfterGranted',
        orElse: () => fail(
            'Expected getToken.nullAfterGranted report, got: $capturedReports'),
      );
      expect(report.area, 'push');
      expect(report.error, isA<StateError>());
      expect(report.extras!['auth_status'], 'authorized');
    });

    test('C — backend throws DioException with response → registerToken.backend',
        () async {
      final fakeMessaging = _FakePushMessagingClient(
        settings: _settings(AuthorizationStatus.authorized),
        tokenBehavior: _ReturnToken('abcdefghij-12345'),
      );
      final dioError = DioException(
        requestOptions: RequestOptions(path: '/v1/users/me/push-tokens'),
        response: Response(
          requestOptions: RequestOptions(path: '/v1/users/me/push-tokens'),
          statusCode: 503,
        ),
        type: DioExceptionType.badResponse,
      );
      final service = _TestablePushNotificationService(
        _FakeApiClient(registerThrows: dioError),
        messagingClient: fakeMessaging,
      );

      await service.ensureRegistered();

      final report = capturedReports.singleWhere(
        (r) => r.operation == 'registerToken.backend',
        orElse: () => fail(
            'Expected registerToken.backend report, got: $capturedReports'),
      );
      expect(report.area, 'push');
      expect(report.error, same(dioError));
      expect(report.extras!['backend_status_code'], 503);
      expect(report.extras!['fcm_token_prefix'], 'abcdefgh');
      expect(report.extras!['auth_status'], 'authorized');
    });
  });

  group('PushNotificationService — MethodChannel handler', () {
    test('apnsRegistrationFailed → reports apns.registrationFailed', () async {
      final fakeMessaging = _FakePushMessagingClient(
        settings: _settings(AuthorizationStatus.authorized),
        tokenBehavior: _ReturnToken('tkn12345xyz'),
      );
      final service = _TestablePushNotificationService(
        _FakeApiClient(),
        messagingClient: fakeMessaging,
      );

      await service.handleNativePushMethod(const MethodCall(
        'apnsRegistrationFailed',
        {
          'domain': 'NSURLErrorDomain',
          'code': -1009,
          'description': 'Offline',
        },
      ));

      final report = capturedReports.singleWhere(
        (r) => r.operation == 'apns.registrationFailed',
        orElse: () =>
            fail('Expected apns.registrationFailed, got: $capturedReports'),
      );
      expect(report.area, 'push');
      expect(report.error, isA<PlatformException>());
      expect(report.extras!['ios_error_domain'], 'NSURLErrorDomain');
      expect(report.extras!['ios_error_code'], -1009);
    });

    test('apnsRegistrationTimeout → reports apns.registrationTimeout',
        () async {
      final fakeMessaging = _FakePushMessagingClient(
        settings: _settings(AuthorizationStatus.authorized),
      );
      final service = _TestablePushNotificationService(
        _FakeApiClient(),
        messagingClient: fakeMessaging,
      );

      await service.handleNativePushMethod(
        const MethodCall('apnsRegistrationTimeout'),
      );

      final report = capturedReports.singleWhere(
        (r) => r.operation == 'apns.registrationTimeout',
        orElse: () =>
            fail('Expected apns.registrationTimeout, got: $capturedReports'),
      );
      expect(report.error, isA<TimeoutException>());
    });
  });
}

/// Subclass that forces [isAvailable] to true regardless of host platform,
/// so the unit tests exercise the iOS code path when running on macOS in CI.
class _TestablePushNotificationService extends PushNotificationService {
  _TestablePushNotificationService(
    super.apiClient, {
    super.messagingClient,
    super.channel,
  });

  @override
  bool get isAvailable => true;
}

class _ReportCall {
  _ReportCall({
    required this.error,
    this.area,
    this.operation,
    this.extras,
    this.fatal = false,
  });
  final Object error;
  final String? area;
  final String? operation;
  final Map<String, Object?>? extras;
  final bool fatal;
}

NotificationSettings _settings(AuthorizationStatus status) => NotificationSettings(
      alert: AppleNotificationSetting.enabled,
      announcement: AppleNotificationSetting.disabled,
      authorizationStatus: status,
      badge: AppleNotificationSetting.enabled,
      carPlay: AppleNotificationSetting.disabled,
      lockScreen: AppleNotificationSetting.enabled,
      notificationCenter: AppleNotificationSetting.enabled,
      showPreviews: AppleShowPreviewSetting.always,
      timeSensitive: AppleNotificationSetting.disabled,
      criticalAlert: AppleNotificationSetting.disabled,
      sound: AppleNotificationSetting.enabled,
      providesAppNotificationSettings: AppleNotificationSetting.disabled,
    );

abstract class _TokenBehavior {
  Future<String?> resolve();
}

class _ReturnToken implements _TokenBehavior {
  _ReturnToken(this.token);
  final String token;
  @override
  Future<String?> resolve() async => token;
}

class _ReturnNull implements _TokenBehavior {
  @override
  Future<String?> resolve() async => null;
}

class _Throw implements _PermissionBehavior {
  _Throw(this.error);
  final Object error;
  @override
  Future<NotificationSettings> resolve() async => throw error;
}

abstract class _PermissionBehavior {
  Future<NotificationSettings> resolve();
}

class _FakePushMessagingClient implements PushMessagingClient {
  _FakePushMessagingClient({
    required this.settings,
    this.requestPermissionBehavior,
    _TokenBehavior? tokenBehavior,
  }) : tokenBehavior = tokenBehavior ?? _ReturnNull();

  NotificationSettings settings;
  final _PermissionBehavior? requestPermissionBehavior;
  final _TokenBehavior tokenBehavior;

  @override
  Future<NotificationSettings> getNotificationSettings() async => settings;

  @override
  Future<NotificationSettings> requestPermission({
    bool alert = false,
    bool badge = false,
    bool sound = false,
    bool provisional = false,
  }) async {
    final behavior = requestPermissionBehavior;
    if (behavior != null) return behavior.resolve();
    return settings;
  }

  @override
  Future<String?> getToken() => tokenBehavior.resolve();

  @override
  Stream<String> get onTokenRefresh => const Stream.empty();

  @override
  Stream<RemoteMessage> get onMessage => const Stream.empty();

  @override
  Stream<RemoteMessage> get onMessageOpenedApp => const Stream.empty();

  @override
  Future<RemoteMessage?> getInitialMessage() async => null;

  @override
  Future<void> subscribeToTopic(String topic) async {}

  @override
  Future<void> unsubscribeFromTopic(String topic) async {}

  @override
  void registerBackgroundHandler() {}
}

class _FakeApiClient extends ApiClient {
  _FakeApiClient({this.registerThrows});
  final Object? registerThrows;

  @override
  Future<Response> registerPushToken({
    required String token,
    String? deviceType,
    String? deviceName,
  }) async {
    final err = registerThrows;
    if (err != null) throw err;
    return Response(
      requestOptions: RequestOptions(path: '/v1/users/me/push-tokens'),
      statusCode: 200,
    );
  }

  @override
  Future<Response> unregisterPushToken(String token) async {
    return Response(
      requestOptions: RequestOptions(path: '/v1/users/me/push-tokens'),
      statusCode: 200,
    );
  }
}
