import 'dart:async';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/services.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
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

      // autoPrompt: true forces the service into the requestPermission
      // path so the fake's _Throw fires and we can assert the outer report.
      final result = await service.ensureRegistered(autoPrompt: true);

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

  group('PushNotificationService — Android channel creation', () {
    test('Android path creates palateful_default channel once', () async {
      final fakeMessaging = _FakePushMessagingClient(
        settings: _settings(AuthorizationStatus.authorized),
        tokenBehavior: _ReturnToken('tkn1234567890'),
      );
      final fakeLocal = _FakeLocalNotificationsClient();
      final service = _AndroidPushNotificationService(
        _FakeApiClient(),
        messagingClient: fakeMessaging,
        localNotificationsClient: fakeLocal,
      );

      await service.ensureRegistered();
      await service.ensureRegistered();

      expect(fakeLocal.createdChannels, hasLength(1));
      final channel = fakeLocal.createdChannels.single;
      expect(channel.id, 'palateful_default');
      expect(channel.name, 'Palateful Notifications');
      expect(channel.importance, Importance.high);
      expect(channel.showBadge, isTrue);
      expect(
        capturedReports.where((r) => r.operation == 'androidChannel.create'),
        isEmpty,
      );
    });

    test('Non-Android path does not create any channel', () async {
      final fakeMessaging = _FakePushMessagingClient(
        settings: _settings(AuthorizationStatus.authorized),
        tokenBehavior: _ReturnToken('tkn1234567890'),
      );
      final fakeLocal = _FakeLocalNotificationsClient();
      final service = _TestablePushNotificationService(
        _FakeApiClient(),
        messagingClient: fakeMessaging,
        localNotificationsClient: fakeLocal,
      );

      await service.ensureRegistered();

      expect(fakeLocal.createdChannels, isEmpty);
    });

    test('Channel creation failure reports androidChannel.create', () async {
      final fakeMessaging = _FakePushMessagingClient(
        settings: _settings(AuthorizationStatus.authorized),
        tokenBehavior: _ReturnToken('tkn1234567890'),
      );
      final fakeLocal = _FakeLocalNotificationsClient(
        throwOnCreate: StateError('native channel create failed'),
      );
      final service = _AndroidPushNotificationService(
        _FakeApiClient(),
        messagingClient: fakeMessaging,
        localNotificationsClient: fakeLocal,
      );

      await service.ensureRegistered();

      final report = capturedReports.singleWhere(
        (r) => r.operation == 'androidChannel.create',
        orElse: () =>
            fail('Expected androidChannel.create report, got: $capturedReports'),
      );
      expect(report.area, 'push');
      expect(report.error, isA<StateError>());
      expect(report.extras!['channel_id'], 'palateful_default');
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

  // push-diag-2: autoPrompt gating + Firebase readiness + 3-strike retry +
  // breadcrumb ordering.
  group('PushNotificationService — push-diag-2 (ensureRegistered hardening)',
      () {
    test('A — Firebase not initialized → reports firebaseNotReady', () async {
      final fakeMessaging = _FakePushMessagingClient(
        settings: _settings(AuthorizationStatus.notDetermined),
      );
      final service = _TestablePushNotificationService(
        _FakeApiClient(),
        messagingClient: fakeMessaging,
        firebaseReady: false,
      );

      final result = await service.ensureRegistered(autoPrompt: true);

      expect(result, AuthorizationStatus.notDetermined);
      final report = capturedReports.singleWhere(
        (r) => r.operation == 'ensureRegistered.firebaseNotReady',
        orElse: () => fail(
            'Expected firebaseNotReady report, got: $capturedReports'),
      );
      expect(report.area, 'push');
      expect(report.error, isA<StateError>());
    });

    test(
        'B — notDetermined + autoPrompt=true across 4 calls → requestPermission '
        'called exactly 3 times', () async {
      final fake = _FakePushMessagingClient(
        settings: _settings(AuthorizationStatus.notDetermined),
      );
      // Configure requestPermission to keep returning notDetermined (OS
      // prompt was suppressed). This is the retry-exhaustion path.
      fake.requestPermissionBehavior = _ReturnSettings(
        _settings(AuthorizationStatus.notDetermined),
      );

      final service = _TestablePushNotificationService(
        _FakeApiClient(),
        messagingClient: fake,
      );

      for (var i = 0; i < 4; i++) {
        await service.ensureRegistered(autoPrompt: true);
      }

      expect(fake.requestPermissionCalls, 3);
      expect(service.requestAttempts, 3);
    });

    test(
        'C — notDetermined → authorized on first call → requestPermission called '
        'once, no re-prompt on subsequent calls', () async {
      final fake = _FakePushMessagingClient(
        settings: _settings(AuthorizationStatus.notDetermined),
      );
      // First (and only) requestPermission call returns authorized AND
      // updates the fake baseline so subsequent getNotificationSettings
      // returns authorized, not notDetermined.
      final service = _TestablePushNotificationService(
        _FakeApiClient(),
        messagingClient: fake,
      );
      fake.requestPermissionBehavior = _ReturnSettingsAndUpdate(
        _settings(AuthorizationStatus.authorized),
        fake,
      );

      await service.ensureRegistered(autoPrompt: true);
      await service.ensureRegistered(autoPrompt: true);
      await service.ensureRegistered(autoPrompt: true);

      expect(fake.requestPermissionCalls, 1);
      expect(service.requestAttempts, 1);
    });

    test('D — denied → requestPermission not called, breadcrumb emitted',
        () async {
      final fake = _FakePushMessagingClient(
        settings: _settings(AuthorizationStatus.denied),
      );
      final service = _TestablePushNotificationService(
        _FakeApiClient(),
        messagingClient: fake,
      );

      await service.ensureRegistered(autoPrompt: true);

      expect(fake.requestPermissionCalls, 0);
      expect(service.requestAttempts, 0);
      expect(
        capturedLogs.any((l) => l.contains('denied, no-op')),
        isTrue,
        reason: 'Expected a denied-no-op breadcrumb, got: $capturedLogs',
      );
    });

    test(
        'E — breadcrumbs fire in documented order on notDetermined → authorized',
        () async {
      final fake = _FakePushMessagingClient(
        settings: _settings(AuthorizationStatus.notDetermined),
      );
      final service = _TestablePushNotificationService(
        _FakeApiClient(),
        messagingClient: fake,
      );
      fake.requestPermissionBehavior = _ReturnSettingsAndUpdate(
        _settings(AuthorizationStatus.authorized),
        fake,
      );

      await service.ensureRegistered(autoPrompt: true);

      final enteredIdx = capturedLogs.indexWhere((l) => l.contains('entered'));
      final statusIdx = capturedLogs
          .indexWhere((l) => l.startsWith('push.ensureRegistered: status='));
      final callingIdx = capturedLogs
          .indexWhere((l) => l.contains('calling requestPermission'));
      final postPromptIdx =
          capturedLogs.indexWhere((l) => l.contains('post-prompt'));
      final grantedIdx =
          capturedLogs.indexWhere((l) => l.contains('granted, fetching token'));
      final completedIdx =
          capturedLogs.indexWhere((l) => l.contains('completed, '));

      expect(enteredIdx, isNonNegative);
      expect(enteredIdx, lessThan(statusIdx));
      expect(statusIdx, lessThan(callingIdx));
      expect(callingIdx, lessThan(postPromptIdx));
      expect(postPromptIdx, lessThan(grantedIdx));
      expect(grantedIdx, lessThan(completedIdx));
    });

    test(
        'F — autoPrompt=false + notDetermined → requestPermission NOT called, '
        'skip breadcrumb emitted', () async {
      final fake = _FakePushMessagingClient(
        settings: _settings(AuthorizationStatus.notDetermined),
      );
      final service = _TestablePushNotificationService(
        _FakeApiClient(),
        messagingClient: fake,
      );

      await service.ensureRegistered(autoPrompt: false);

      expect(fake.requestPermissionCalls, 0);
      expect(service.requestAttempts, 0);
      expect(
        capturedLogs.any(
          (l) => l.contains('autoPrompt=false, skipping requestPermission'),
        ),
        isTrue,
        reason: 'Expected skip breadcrumb, got: $capturedLogs',
      );
    });

    test(
        'G — autoPrompt=false + authorized → getToken IS called (token refresh '
        'not blocked)', () async {
      final fake = _FakePushMessagingClient(
        settings: _settings(AuthorizationStatus.authorized),
        tokenBehavior: _ReturnToken('ghijklmn-xyz'),
      );
      final api = _FakeApiClient();
      final service = _TestablePushNotificationService(
        api,
        messagingClient: fake,
      );

      await service.ensureRegistered(autoPrompt: false);

      expect(api.registerCalls, 1);
      // autoPrompt=false must NOT trigger requestPermission even in the
      // authorized path (status is != notDetermined so the branch is skipped).
      expect(fake.requestPermissionCalls, 0);
    });
  });
}

/// Subclass that forces [isAvailable] to true regardless of host platform
/// and stubs [isFirebaseReady] (production reads `Firebase.apps.isNotEmpty`,
/// which requires a real bootstrap unavailable in unit tests).
class _TestablePushNotificationService extends PushNotificationService {
  _TestablePushNotificationService(
    super.apiClient, {
    super.messagingClient,
    super.localNotificationsClient,
    super.channel,
    this.firebaseReady = true,
  });

  bool firebaseReady;

  @override
  bool get isAvailable => true;

  @override
  bool get isFirebaseReady => firebaseReady;
}

/// Subclass that also forces [isAndroid] to true so macOS-hosted tests
/// can exercise the Android-only channel-creation path.
class _AndroidPushNotificationService extends _TestablePushNotificationService {
  _AndroidPushNotificationService(
    super.apiClient, {
    super.messagingClient,
    super.localNotificationsClient,
  });

  @override
  bool get isAndroid => true;
}

class _FakeLocalNotificationsClient implements LocalNotificationsClient {
  _FakeLocalNotificationsClient({this.throwOnCreate});

  final Object? throwOnCreate;
  final List<AndroidNotificationChannel> createdChannels = [];

  @override
  Future<void> createAndroidChannel(AndroidNotificationChannel channel) async {
    final err = throwOnCreate;
    if (err != null) throw err;
    createdChannels.add(channel);
  }
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
  Future<NotificationSettings> resolve(_FakePushMessagingClient _) async =>
      throw error;
}

class _ReturnSettings implements _PermissionBehavior {
  _ReturnSettings(this.toReturn);
  final NotificationSettings toReturn;
  @override
  Future<NotificationSettings> resolve(_FakePushMessagingClient _) async =>
      toReturn;
}

/// Returns the given settings AND mutates the fake's baseline so
/// subsequent `getNotificationSettings()` calls observe the new status.
/// Used for the "grant on first prompt" path.
class _ReturnSettingsAndUpdate implements _PermissionBehavior {
  _ReturnSettingsAndUpdate(this.toReturn, this._fake);
  final NotificationSettings toReturn;
  final _FakePushMessagingClient _fake;
  @override
  Future<NotificationSettings> resolve(_FakePushMessagingClient _) async {
    _fake.settings = toReturn;
    return toReturn;
  }
}

abstract class _PermissionBehavior {
  Future<NotificationSettings> resolve(_FakePushMessagingClient owner);
}

class _FakePushMessagingClient implements PushMessagingClient {
  _FakePushMessagingClient({
    required this.settings,
    this.requestPermissionBehavior,
    _TokenBehavior? tokenBehavior,
  }) : tokenBehavior = tokenBehavior ?? _ReturnNull();

  NotificationSettings settings;
  _PermissionBehavior? requestPermissionBehavior;
  final _TokenBehavior tokenBehavior;
  int requestPermissionCalls = 0;

  @override
  Future<NotificationSettings> getNotificationSettings() async => settings;

  @override
  Future<NotificationSettings> requestPermission({
    bool alert = false,
    bool badge = false,
    bool sound = false,
    bool provisional = false,
  }) async {
    requestPermissionCalls++;
    final behavior = requestPermissionBehavior;
    if (behavior != null) return behavior.resolve(this);
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
  int registerCalls = 0;

  @override
  Future<Response> registerPushToken({
    required String token,
    String? deviceType,
    String? deviceName,
  }) async {
    registerCalls++;
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
