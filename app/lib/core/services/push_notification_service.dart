import 'dart:io';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';

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
  bool _initialized = false;

  PushNotificationService(this._apiClient);

  /// Check if push notifications are available on this platform.
  bool get isAvailable => !kIsWeb && (Platform.isIOS || Platform.isAndroid);

  /// Get the current FCM token.
  String? get currentToken => _currentToken;

  /// Initialize Firebase and set up push notifications.
  Future<void> initialize() async {
    if (_initialized || !isAvailable) return;

    try {
      // Set up background handler
      FirebaseMessaging.onBackgroundMessage(
          _firebaseMessagingBackgroundHandler);

      // Request permission (required for iOS, optional for Android 13+)
      final settings = await _messaging.requestPermission(
        alert: true,
        badge: true,
        sound: true,
        provisional: false,
      );

      if (settings.authorizationStatus == AuthorizationStatus.authorized ||
          settings.authorizationStatus == AuthorizationStatus.provisional) {
        debugPrint('Push notification permission granted');

        // Get and register token
        await _getAndRegisterToken();

        // Listen for token refresh
        _messaging.onTokenRefresh.listen(_onTokenRefresh);

        // Handle foreground messages
        FirebaseMessaging.onMessage.listen(_onForegroundMessage);

        // Handle notification taps when app is in background
        FirebaseMessaging.onMessageOpenedApp.listen(_onMessageOpenedApp);

        // Check if app was opened from a notification
        final initialMessage = await _messaging.getInitialMessage();
        if (initialMessage != null) {
          _handleNotificationTap(initialMessage);
        }

        _initialized = true;
        debugPrint('Push notification service initialized');
      } else {
        debugPrint('Push notification permission denied');
      }
    } catch (e) {
      debugPrint('Failed to initialize push notifications: $e');
    }
  }

  /// Get FCM token and register with backend.
  Future<void> _getAndRegisterToken() async {
    try {
      final token = await _messaging.getToken();
      if (token != null) {
        _currentToken = token;
        await _registerTokenWithBackend(token);
      }
    } catch (e) {
      debugPrint('Failed to get FCM token: $e');
    }
  }

  /// Handle token refresh.
  void _onTokenRefresh(String token) async {
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

  /// Handle foreground messages.
  void _onForegroundMessage(RemoteMessage message) {
    debugPrint('Foreground message: ${message.notification?.title}');

    // You can show a local notification here or update UI
    // For now, we'll just log it - in a real app, you'd want to
    // show an in-app notification or update relevant state
    _handleNotificationData(message);
  }

  /// Handle notification tap when app is in background.
  void _onMessageOpenedApp(RemoteMessage message) {
    debugPrint('Notification opened app: ${message.notification?.title}');
    _handleNotificationTap(message);
  }

  /// Handle notification data payload.
  void _handleNotificationData(RemoteMessage message) {
    final data = message.data;
    final notificationType = data['notification_type'];

    debugPrint('Notification type: $notificationType');
    debugPrint('Notification data: $data');

    // Handle different notification types
    // This would typically update app state or trigger navigation
  }

  /// Handle notification tap - navigate to relevant screen.
  void _handleNotificationTap(RemoteMessage message) {
    final data = message.data;
    final notificationType = data['notification_type'];

    debugPrint('Handling notification tap: $notificationType');

    // Navigate based on notification type
    // This would typically use your router to navigate to the relevant screen
    switch (notificationType) {
      case 'shopping_item_added':
      case 'shopping_item_checked':
      case 'shopping_list_shared':
      case 'shopping_deadline_reminder':
      case 'shopping_list_complete':
        final shoppingListId = data['shopping_list_id'];
        if (shoppingListId != null) {
          // Navigate to shopping list
          debugPrint('Navigate to shopping list: $shoppingListId');
        }
        break;

      case 'recipe_book_shared':
      case 'recipe_added':
        final recipeBookId = data['recipe_book_id'];
        if (recipeBookId != null) {
          // Navigate to recipe book
          debugPrint('Navigate to recipe book: $recipeBookId');
        }
        break;

      case 'meal_event_invite':
      case 'meal_event_reminder':
      case 'meal_event_updated':
        final mealEventId = data['meal_event_id'];
        if (mealEventId != null) {
          // Navigate to meal event
          debugPrint('Navigate to meal event: $mealEventId');
        }
        break;

      default:
        debugPrint('Unknown notification type: $notificationType');
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
