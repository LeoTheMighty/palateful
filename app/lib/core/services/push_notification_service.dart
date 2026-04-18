import 'dart:async';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:url_launcher/url_launcher.dart';

import '../router/app_router.dart';
import 'api_client.dart';
import 'error_reporter.dart';

/// FCM channel id the backend declares in `android.notification.channel_id`.
/// Mirrored server-side in `libraries/utils/utils/services/push_notification.py`
/// as the `PushNotification.channel_id` default. Keep both in sync.
const String palatefulDefaultChannelId = 'palateful_default';
const String _palatefulDefaultChannelName = 'Palateful Notifications';
const String _palatefulDefaultChannelDescription =
    'General notifications from Palateful.';

/// Background message handler - must be top-level function
@pragma('vm:entry-point')
Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp();
  debugPrint('Background message: ${message.messageId}');
}

/// Thin wrapper around [FirebaseMessaging] used by [PushNotificationService]
/// so Firebase calls can be faked in unit tests. Production wiring uses
/// [FirebaseMessagingClient]; tests supply a fake.
abstract class PushMessagingClient {
  Future<NotificationSettings> getNotificationSettings();
  Future<NotificationSettings> requestPermission({
    bool alert,
    bool badge,
    bool sound,
    bool provisional,
  });
  Future<String?> getToken();
  Stream<String> get onTokenRefresh;
  Stream<RemoteMessage> get onMessage;
  Stream<RemoteMessage> get onMessageOpenedApp;
  Future<RemoteMessage?> getInitialMessage();
  Future<void> subscribeToTopic(String topic);
  Future<void> unsubscribeFromTopic(String topic);
  void registerBackgroundHandler();
}

/// Thin wrapper around `flutter_local_notifications` for Android channel
/// management. Keeps channel creation behind an injection seam so unit
/// tests can assert creation without hitting native code.
abstract class LocalNotificationsClient {
  Future<void> createAndroidChannel(AndroidNotificationChannel channel);
}

class FlutterLocalNotificationsClient implements LocalNotificationsClient {
  final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();

  @override
  Future<void> createAndroidChannel(AndroidNotificationChannel channel) async {
    await _plugin
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(channel);
  }
}

class FirebaseMessagingClient implements PushMessagingClient {
  final FirebaseMessaging _messaging = FirebaseMessaging.instance;

  @override
  Future<NotificationSettings> getNotificationSettings() =>
      _messaging.getNotificationSettings();

  @override
  Future<NotificationSettings> requestPermission({
    bool alert = false,
    bool badge = false,
    bool sound = false,
    bool provisional = false,
  }) =>
      _messaging.requestPermission(
        alert: alert,
        badge: badge,
        sound: sound,
        provisional: provisional,
      );

  @override
  Future<String?> getToken() => _messaging.getToken();

  @override
  Stream<String> get onTokenRefresh => _messaging.onTokenRefresh;

  @override
  Stream<RemoteMessage> get onMessage => FirebaseMessaging.onMessage;

  @override
  Stream<RemoteMessage> get onMessageOpenedApp =>
      FirebaseMessaging.onMessageOpenedApp;

  @override
  Future<RemoteMessage?> getInitialMessage() => _messaging.getInitialMessage();

  @override
  Future<void> subscribeToTopic(String topic) =>
      _messaging.subscribeToTopic(topic);

  @override
  Future<void> unsubscribeFromTopic(String topic) =>
      _messaging.unsubscribeFromTopic(topic);

  @override
  void registerBackgroundHandler() {
    FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);
  }
}

/// MethodChannel used by iOS AppDelegate to forward APNs registration
/// failures (didFailToRegisterForRemoteNotifications + 10s timeout) to
/// Flutter so they reach Crashlytics via [ErrorReporter]. Android has no
/// equivalent path today.
@visibleForTesting
const pushMethodChannelName = 'palateful/push';

/// Service for managing push notifications via Firebase Cloud Messaging.
class PushNotificationService {
  final ApiClient _apiClient;
  final PushMessagingClient _messaging;
  final LocalNotificationsClient _localNotifications;
  final MethodChannel _channel;

  String? _currentToken;
  bool _listenersAttached = false;
  bool _androidChannelCreated = false;
  bool _initialMessageHandled = false;
  GlobalKey<NavigatorState>? _navigatorKey;

  /// In-session count of `requestPermission` invocations that the boot-path
  /// has issued. Capped at [_maxRequestAttempts] per app launch so a broken
  /// Firebase-messaging channel can't re-prompt the user every resume.
  /// Resets on cold start (singleton reconstructed when the process restarts).
  int _requestAttempts = 0;
  static const int _maxRequestAttempts = 3;

  @visibleForTesting
  int get requestAttempts => _requestAttempts;

  PushNotificationService(
    this._apiClient, {
    PushMessagingClient? messagingClient,
    LocalNotificationsClient? localNotificationsClient,
    MethodChannel? channel,
  })  : _messaging = messagingClient ?? FirebaseMessagingClient(),
        _localNotifications =
            localNotificationsClient ?? FlutterLocalNotificationsClient(),
        _channel = channel ?? const MethodChannel(pushMethodChannelName);

  /// Override point for tests running on macOS that need to exercise the
  /// Android branch of [_ensureAndroidChannel]. Production reads
  /// `Platform.isAndroid`.
  @visibleForTesting
  bool get isAndroid => Platform.isAndroid;

  /// Override point for tests that simulate the firebase-not-initialized
  /// race. Production reads `Firebase.apps.isNotEmpty`.
  @visibleForTesting
  bool get isFirebaseReady => Firebase.apps.isNotEmpty;

  /// Check if push notifications are available on this platform.
  bool get isAvailable => !kIsWeb && (Platform.isIOS || Platform.isAndroid);

  /// Get the current FCM token.
  String? get currentToken => _currentToken;

  /// Set the navigator key for showing in-app notifications.
  void setNavigatorKey(GlobalKey<NavigatorState> key) {
    _navigatorKey = key;
  }

  String get _platform => Platform.isIOS ? 'ios' : 'android';

  /// Read the OS-level authorization status without prompting the user.
  Future<AuthorizationStatus> getPermissionStatus() async {
    if (!isAvailable) return AuthorizationStatus.notDetermined;
    final settings = await _messaging.getNotificationSettings();
    return settings.authorizationStatus;
  }

  /// Initialize Firebase handlers and register the FCM token with the backend.
  ///
  /// Safe to call repeatedly — on app launch, on foreground resume, and when the
  /// user toggles the push preference on. Behaviour:
  ///   - Wires OS-level listeners exactly once (idempotent).
  ///   - When [autoPrompt] is true AND status is `notDetermined`, fires the
  ///     OS permission prompt (bounded to [_maxRequestAttempts] per app launch).
  ///   - When [autoPrompt] is false, DOES NOT call `requestPermission` — the
  ///     caller owns the prompt (notif-4 onboarding step or a user-initiated
  ///     tap on Profile → Notifications).
  ///   - Fetches a fresh FCM token and POSTs it to the backend when granted.
  ///
  /// Defaults to `autoPrompt: false` so every call site explicitly opts in
  /// to prompting.
  ///
  /// Returns the resulting OS authorization status so callers can branch on it
  /// (e.g. deep-link to Settings when `denied`).
  Future<AuthorizationStatus> ensureRegistered({bool autoPrompt = false}) async {
    if (!isAvailable) return AuthorizationStatus.notDetermined;

    ErrorReporter.log(
      'push.ensureRegistered: entered, platform=$_platform, '
      'autoPrompt=$autoPrompt, attempts=$_requestAttempts',
    );

    // Firebase readiness guard: if Firebase.initializeApp() hasn't completed
    // upstream (race at cold start), bail loudly so the subsequent
    // FirebaseMessaging calls don't fail with a cryptic MissingPluginException.
    if (!isFirebaseReady) {
      ErrorReporter.report(
        StateError('Firebase not initialized in ensureRegistered'),
        StackTrace.current,
        area: 'push',
        operation: 'ensureRegistered.firebaseNotReady',
        extras: {'platform': _platform, 'autoPrompt': autoPrompt},
      );
      return AuthorizationStatus.notDetermined;
    }

    try {
      if (!_listenersAttached) {
        _messaging.registerBackgroundHandler();
        _messaging.onTokenRefresh.listen(_onTokenRefresh);
        _messaging.onMessage.listen(_onForegroundMessage);
        _messaging.onMessageOpenedApp.listen(_onMessageOpenedApp);
        _channel.setMethodCallHandler(_handleNativePushMethod);
        _listenersAttached = true;
      }

      await _ensureAndroidChannel();

      var settings = await _messaging.getNotificationSettings();
      ErrorReporter.log(
        'push.ensureRegistered: status=${settings.authorizationStatus.name}',
      );

      if (settings.authorizationStatus == AuthorizationStatus.notDetermined) {
        if (!autoPrompt) {
          ErrorReporter.log(
            'push.ensureRegistered: autoPrompt=false, skipping requestPermission',
          );
        } else if (_requestAttempts >= _maxRequestAttempts) {
          ErrorReporter.log(
            'push.ensureRegistered: max retry attempts reached this launch '
            '(attempts=$_requestAttempts)',
          );
        } else {
          ErrorReporter.log(
            'push.ensureRegistered: calling requestPermission '
            '(attempt ${_requestAttempts + 1}/$_maxRequestAttempts)',
          );
          settings = await _messaging.requestPermission(
            alert: true,
            badge: true,
            sound: true,
            provisional: false,
          );
          _requestAttempts++;
          ErrorReporter.log(
            'push.ensureRegistered: post-prompt status='
            '${settings.authorizationStatus.name}',
          );
          if (settings.authorizationStatus ==
              AuthorizationStatus.notDetermined) {
            ErrorReporter.log(
              'push: requestPermission returned notDetermined, '
              'attempts=$_requestAttempts',
            );
          }
        }
      }

      debugPrint(
        'Push permission: ${settings.authorizationStatus}',
      );

      final granted =
          settings.authorizationStatus == AuthorizationStatus.authorized ||
              settings.authorizationStatus == AuthorizationStatus.provisional;

      if (granted) {
        ErrorReporter.log(
          'push.ensureRegistered: granted, fetching token',
        );
        await _getAndRegisterToken(settings.authorizationStatus);

        if (!_initialMessageHandled) {
          final initialMessage = await _messaging.getInitialMessage();
          if (initialMessage != null) {
            _navigateToRoute(initialMessage, usePush: false);
          }
          _initialMessageHandled = true;
        }
      } else if (settings.authorizationStatus == AuthorizationStatus.denied) {
        ErrorReporter.log('push.ensureRegistered: denied, no-op');
      }

      ErrorReporter.log(
        'push.ensureRegistered: completed, '
        'final_status=${settings.authorizationStatus.name}, '
        'attempts=$_requestAttempts',
      );

      return settings.authorizationStatus;
    } catch (e, st) {
      ErrorReporter.report(
        e,
        st,
        area: 'push',
        operation: 'ensureRegistered.outer',
        extras: {'platform': _platform, 'autoPrompt': autoPrompt},
      );
      return AuthorizationStatus.notDetermined;
    }
  }

  /// Legacy alias retained for existing call sites — opts out of the
  /// boot-time auto-prompt. New code should call [ensureRegistered]
  /// directly with an explicit `autoPrompt:` decision.
  Future<void> initialize() => ensureRegistered(autoPrompt: false);

  /// Create the `palateful_default` notification channel on Android so
  /// incoming FCM payloads (which declare matching
  /// `android.notification.channel_id`) surface under a named,
  /// user-controllable channel instead of the system default bucket.
  /// No-op on non-Android platforms or after the first successful call.
  Future<void> _ensureAndroidChannel() async {
    if (!isAndroid || _androidChannelCreated) return;
    try {
      await _localNotifications.createAndroidChannel(
        const AndroidNotificationChannel(
          palatefulDefaultChannelId,
          _palatefulDefaultChannelName,
          description: _palatefulDefaultChannelDescription,
          importance: Importance.high,
          showBadge: true,
        ),
      );
      _androidChannelCreated = true;
    } catch (e, st) {
      ErrorReporter.report(
        e,
        st,
        area: 'push',
        operation: 'androidChannel.create',
        extras: {'platform': _platform, 'channel_id': palatefulDefaultChannelId},
      );
    }
  }

  /// Open this app's page in the OS Settings so the user can grant/revoke
  /// notification permission. iOS-only today; Android would need a dedicated
  /// package (e.g. `permission_handler`) for a reliable deep link.
  Future<bool> openOsSettings() async {
    if (!isAvailable) return false;
    try {
      if (Platform.isIOS) {
        return await launchUrl(Uri.parse('app-settings:'));
      }
      return false;
    } catch (e, st) {
      ErrorReporter.report(
        e,
        st,
        area: 'push',
        operation: 'openOsSettings',
        extras: {'platform': _platform},
      );
      return false;
    }
  }

  /// Get FCM token and register with backend.
  Future<void> _getAndRegisterToken(AuthorizationStatus authStatus) async {
    try {
      final token = await _messaging.getToken();
      if (token != null) {
        _currentToken = token;
        debugPrint(
          'FCM token: ${token.substring(0, token.length < 12 ? token.length : 12)}…',
        );
        await _registerTokenWithBackend(token, authStatus);
      } else {
        ErrorReporter.report(
          StateError('FCM token null after granted permission'),
          StackTrace.current,
          area: 'push',
          operation: 'getToken.nullAfterGranted',
          extras: {
            'platform': _platform,
            'auth_status': authStatus.name,
          },
        );
      }
    } catch (e, st) {
      ErrorReporter.report(
        e,
        st,
        area: 'push',
        operation: 'getToken.exception',
        extras: {
          'platform': _platform,
          'auth_status': authStatus.name,
        },
      );
    }
  }

  /// Handle token refresh.
  Future<void> _onTokenRefresh(String token) async {
    debugPrint('FCM token refreshed');
    _currentToken = token;
    final status = await _safePermissionStatus();
    await _registerTokenWithBackend(token, status);
  }

  /// Register token with the backend API.
  Future<void> _registerTokenWithBackend(
    String token,
    AuthorizationStatus authStatus,
  ) async {
    try {
      final deviceType = Platform.isIOS ? 'ios' : 'android';
      await _apiClient.registerPushToken(
        token: token,
        deviceType: deviceType,
      );
      debugPrint('Push token registered with backend');
    } catch (e, st) {
      ErrorReporter.report(
        e,
        st,
        area: 'push',
        operation: 'registerToken.backend',
        extras: {
          'platform': _platform,
          'auth_status': authStatus.name,
          'fcm_token_prefix': _tokenPrefix(token),
          'backend_status_code': _statusCodeOf(e),
        },
      );
    }
  }

  /// Unregister current token from backend (call on logout).
  Future<void> unregisterToken() async {
    final token = _currentToken;
    if (token != null) {
      try {
        await _apiClient.unregisterPushToken(token);
        debugPrint('Push token unregistered');
      } catch (e, st) {
        ErrorReporter.report(
          e,
          st,
          area: 'push',
          operation: 'unregisterToken.backend',
          extras: {
            'platform': _platform,
            'fcm_token_prefix': _tokenPrefix(token),
            'backend_status_code': _statusCodeOf(e),
          },
        );
      }
    }
    _currentToken = null;
  }

  /// Handle foreground messages — show in-app banner.
  void _onForegroundMessage(RemoteMessage message) {
    debugPrint('Foreground message: ${message.notification?.title}');

    final context = _navigatorKey?.currentContext;
    if (context == null) return;

    final title = message.notification?.title ?? '';
    final body = message.notification?.body ?? '';
    if (title.isEmpty && body.isEmpty) return;

    try {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (title.isNotEmpty)
                Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
              if (body.isNotEmpty) Text(body),
            ],
          ),
          duration: const Duration(seconds: 4),
          behavior: SnackBarBehavior.floating,
          action: SnackBarAction(
            label: 'View',
            onPressed: () => _navigateToRoute(message, usePush: true),
          ),
        ),
      );
    } catch (e, st) {
      ErrorReporter.report(
        e,
        st,
        area: 'push',
        operation: 'foregroundBanner.show',
        extras: {'platform': _platform},
      );
    }
  }

  /// Handle notification tap when app is in background.
  void _onMessageOpenedApp(RemoteMessage message) {
    debugPrint('Notification opened app: ${message.notification?.title}');
    _navigateToRoute(message, usePush: false);
  }

  /// Navigate to the route for a notification.
  /// [usePush] true for foreground taps (preserves nav stack), false for cold/background start.
  void _navigateToRoute(RemoteMessage message, {required bool usePush}) {
    final data = message.data;
    final notificationType = data['notification_type'];

    debugPrint('Handling notification tap: $notificationType');

    final route = _routeForNotification(notificationType, data);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (usePush) {
        appRouter.push(route);
      } else if (route.startsWith('/recipe-books')) {
        // Recipe book routes are outside the nav shell — go home first, then push
        appRouter.go('/');
        appRouter.push(route);
      } else {
        appRouter.go(route);
      }
    });
  }

  /// Map notification type to a deep link route.
  String _routeForNotification(String? notificationType, Map<String, dynamic> data) {
    switch (notificationType) {
      case 'import_complete':
      case 'import_needs_attention':
      case 'import_needs_review':
        final jobId = data['import_job_id'];
        if (jobId != null) return '/recipes/import/review-list/$jobId';
        return '/';

      case 'shopping_item_added':
      case 'shopping_item_checked':
      case 'shopping_list_shared':
      case 'shopping_deadline_reminder':
      case 'shopping_list_complete':
        return '/cart';

      case 'recipe_book_shared':
        final bookId = data['recipe_book_id'];
        if (bookId != null) return '/recipe-books/$bookId';
        return '/recipe-books';

      case 'recipe_added':
        final recipeId = data['recipe_id'];
        if (recipeId != null) return '/recipes/$recipeId';
        final bookId = data['recipe_book_id'];
        if (bookId != null) return '/recipe-books/$bookId';
        return '/';

      case 'meal_event_invite':
      case 'meal_event_reminder':
      case 'meal_event_updated':
        return '/calendar';

      case 'friend_request':
      case 'friend_request_accepted':
      case 'invitation_received':
      case 'invitation_accepted':
      case 'member_joined':
        return '/profile';

      case 'new_feedback':
        // Admin-only fan-out. Deep-link to the feedback inbox.
        return '/admin/feedback';

      default:
        return '/';
    }
  }

  /// Subscribe to a topic for broadcast notifications.
  Future<void> subscribeToTopic(String topic) async {
    try {
      await _messaging.subscribeToTopic(topic);
      debugPrint('Subscribed to topic: $topic');
    } catch (e, st) {
      ErrorReporter.report(
        e,
        st,
        area: 'push',
        operation: 'subscribeToTopic',
        extras: {'platform': _platform, 'topic': topic},
      );
    }
  }

  /// Unsubscribe from a topic.
  Future<void> unsubscribeFromTopic(String topic) async {
    try {
      await _messaging.unsubscribeFromTopic(topic);
      debugPrint('Unsubscribed from topic: $topic');
    } catch (e, st) {
      ErrorReporter.report(
        e,
        st,
        area: 'push',
        operation: 'unsubscribeTopic',
        extras: {'platform': _platform, 'topic': topic},
      );
    }
  }

  /// Dispatch calls from the native iOS AppDelegate (APNs registration
  /// failure + 10s registration timeout) into Crashlytics. The native
  /// side invokes these on [pushMethodChannelName]; this handler is the
  /// Flutter receive-side.
  @visibleForTesting
  Future<void> handleNativePushMethod(MethodCall call) =>
      _handleNativePushMethod(call);

  Future<void> _handleNativePushMethod(MethodCall call) async {
    final status = await _safePermissionStatus();
    switch (call.method) {
      case 'apnsRegistrationFailed':
        final args =
            (call.arguments is Map) ? Map<String, Object?>.from(call.arguments) : const <String, Object?>{};
        final domain = args['domain']?.toString() ?? 'unknown';
        final code = args['code'];
        final desc = args['description']?.toString() ?? '';
        ErrorReporter.report(
          PlatformException(
            code: 'apns.registrationFailed',
            message: desc,
            details: {'domain': domain, 'code': code},
          ),
          StackTrace.current,
          area: 'push',
          operation: 'apns.registrationFailed',
          extras: {
            'platform': _platform,
            'auth_status': status.name,
            'ios_error_domain': domain,
            'ios_error_code': code,
          },
        );
        return;
      case 'apnsRegistrationTimeout':
        ErrorReporter.report(
          TimeoutException('APNs registration did not complete within 10s'),
          StackTrace.current,
          area: 'push',
          operation: 'apns.registrationTimeout',
          extras: {'platform': _platform, 'auth_status': status.name},
        );
        return;
      default:
        // Unknown method. Report so regressions surface.
        ErrorReporter.report(
          ArgumentError('Unknown push channel method: ${call.method}'),
          StackTrace.current,
          area: 'push',
          operation: 'channel.unknownMethod',
          extras: {'platform': _platform, 'method': call.method},
        );
    }
  }

  Future<AuthorizationStatus> _safePermissionStatus() async {
    try {
      return await getPermissionStatus();
    } catch (_) {
      return AuthorizationStatus.notDetermined;
    }
  }

  String? _tokenPrefix(String? token) {
    if (token == null || token.isEmpty) return null;
    return token.length < 8 ? token : token.substring(0, 8);
  }

  int? _statusCodeOf(Object error) {
    if (error is DioException) return error.response?.statusCode;
    return null;
  }
}
