import 'dart:io';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../router/app_router.dart';
import 'api_client.dart';

/// Background message handler - must be top-level function
@pragma('vm:entry-point')
Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp();
  debugPrint('Background message: ${message.messageId}');
}

/// Service for managing push notifications via Firebase Cloud Messaging.
class PushNotificationService {
  final ApiClient _apiClient;
  final FirebaseMessaging _messaging = FirebaseMessaging.instance;

  String? _currentToken;
  bool _listenersAttached = false;
  bool _initialMessageHandled = false;
  GlobalKey<NavigatorState>? _navigatorKey;

  PushNotificationService(this._apiClient);

  /// Check if push notifications are available on this platform.
  bool get isAvailable => !kIsWeb && (Platform.isIOS || Platform.isAndroid);

  /// Get the current FCM token.
  String? get currentToken => _currentToken;

  /// Set the navigator key for showing in-app notifications.
  void setNavigatorKey(GlobalKey<NavigatorState> key) {
    _navigatorKey = key;
  }

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
  ///   - Wires OS-level listeners exactly once.
  ///   - Prompts the OS if permission has not yet been determined (iOS will not
  ///     re-prompt if the user previously denied).
  ///   - Fetches a fresh FCM token and POSTs it to the backend when granted.
  ///
  /// Returns the resulting OS authorization status so callers can branch on it
  /// (e.g. deep-link to Settings when `denied`).
  Future<AuthorizationStatus> ensureRegistered() async {
    if (!isAvailable) return AuthorizationStatus.notDetermined;

    try {
      if (!_listenersAttached) {
        FirebaseMessaging.onBackgroundMessage(
            _firebaseMessagingBackgroundHandler);
        _messaging.onTokenRefresh.listen(_onTokenRefresh);
        FirebaseMessaging.onMessage.listen(_onForegroundMessage);
        FirebaseMessaging.onMessageOpenedApp.listen(_onMessageOpenedApp);
        _listenersAttached = true;
      }

      var settings = await _messaging.getNotificationSettings();
      if (settings.authorizationStatus == AuthorizationStatus.notDetermined) {
        settings = await _messaging.requestPermission(
          alert: true,
          badge: true,
          sound: true,
          provisional: false,
        );
      }

      debugPrint(
        'Push permission: ${settings.authorizationStatus}',
      );

      final granted =
          settings.authorizationStatus == AuthorizationStatus.authorized ||
              settings.authorizationStatus == AuthorizationStatus.provisional;

      if (granted) {
        await _getAndRegisterToken();

        if (!_initialMessageHandled) {
          final initialMessage = await _messaging.getInitialMessage();
          if (initialMessage != null) {
            _navigateToRoute(initialMessage, usePush: false);
          }
          _initialMessageHandled = true;
        }
      }

      return settings.authorizationStatus;
    } catch (e) {
      debugPrint('ensureRegistered failed: $e');
      return AuthorizationStatus.notDetermined;
    }
  }

  /// Legacy alias retained for existing call sites.
  Future<void> initialize() => ensureRegistered();

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
    } catch (e) {
      debugPrint('openOsSettings failed: $e');
      return false;
    }
  }

  /// Get FCM token and register with backend.
  Future<void> _getAndRegisterToken() async {
    try {
      final token = await _messaging.getToken();
      if (token != null) {
        _currentToken = token;
        debugPrint(
          'FCM token: ${token.substring(0, token.length < 12 ? token.length : 12)}…',
        );
        await _registerTokenWithBackend(token);
      } else {
        debugPrint('FCM token: null (getToken returned nothing)');
      }
    } catch (e) {
      debugPrint('Failed to get FCM token: $e');
    }
  }

  /// Handle token refresh.
  Future<void> _onTokenRefresh(String token) async {
    debugPrint('FCM token refreshed');
    _currentToken = token;
    await _registerTokenWithBackend(token);
  }

  /// Register token with the backend API.
  Future<void> _registerTokenWithBackend(String token) async {
    try {
      final deviceType = Platform.isIOS ? 'ios' : 'android';
      await _apiClient.registerPushToken(
        token: token,
        deviceType: deviceType,
      );
      debugPrint('Push token registered with backend');
    } catch (e) {
      debugPrint('Failed to register push token: $e');
    }
  }

  /// Unregister current token from backend (call on logout).
  Future<void> unregisterToken() async {
    if (_currentToken != null) {
      try {
        await _apiClient.unregisterPushToken(_currentToken!);
        debugPrint('Push token unregistered');
      } catch (e) {
        debugPrint('Failed to unregister push token: $e');
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
    } catch (e) {
      debugPrint('Failed to show foreground notification banner: $e');
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

      default:
        return '/';
    }
  }

  /// Subscribe to a topic for broadcast notifications.
  Future<void> subscribeToTopic(String topic) async {
    try {
      await _messaging.subscribeToTopic(topic);
      debugPrint('Subscribed to topic: $topic');
    } catch (e) {
      debugPrint('Failed to subscribe to topic: $e');
    }
  }

  /// Unsubscribe from a topic.
  Future<void> unsubscribeFromTopic(String topic) async {
    try {
      await _messaging.unsubscribeFromTopic(topic);
      debugPrint('Unsubscribed from topic: $topic');
    } catch (e) {
      debugPrint('Failed to unsubscribe from topic: $e');
    }
  }
}
