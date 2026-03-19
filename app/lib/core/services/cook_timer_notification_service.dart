import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_timezone/flutter_timezone.dart';
import 'package:timezone/data/latest_all.dart' as tz;
import 'package:timezone/timezone.dart' as tz;

import '../router/app_router.dart';

/// Top-level background handler: fires on Android when app is killed and user
/// taps a timer notification. Must be top-level + @pragma('vm:entry-point').
@pragma('vm:entry-point')
void _cookTimerBackgroundNotificationHandler(NotificationResponse response) {
  final payload = response.payload;
  if (payload != null && payload.isNotEmpty) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      appRouter.push('/recipes/$payload/cook');
    });
  }
}

const _channelId = 'cook_timers';
const _channelName = 'Cooking Timers';
const _channelDesc = 'Alerts when a cooking timer finishes';

/// Service for scheduling and managing local cooking-timer notifications.
class CookTimerNotificationService {
  final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();

  bool _initialized = false;

  /// Initialize the notification plugin and timezone data.
  Future<void> initialize() async {
    if (_initialized) return;

    try {
      // Initialize timezone database and set local timezone
      tz.initializeTimeZones();
      final timezoneName = await FlutterTimezone.getLocalTimezone();
      tz.setLocalLocation(tz.getLocation(timezoneName));

      const androidInit = AndroidInitializationSettings('@mipmap/ic_launcher');
      const iosInit = DarwinInitializationSettings(
        requestAlertPermission: false,
        requestBadgePermission: false,
        requestSoundPermission: false,
      );
      const initSettings = InitializationSettings(
        android: androidInit,
        iOS: iosInit,
      );

      await _plugin.initialize(
        initSettings,
        onDidReceiveNotificationResponse: _onNotificationResponse,
        onDidReceiveBackgroundNotificationResponse:
            _cookTimerBackgroundNotificationHandler,
      );

      // Create Android notification channel
      if (Platform.isAndroid) {
        const channel = AndroidNotificationChannel(
          _channelId,
          _channelName,
          description: _channelDesc,
          importance: Importance.max,
          playSound: true,
        );
        await _plugin
            .resolvePlatformSpecificImplementation<
                AndroidFlutterLocalNotificationsPlugin>()
            ?.createNotificationChannel(channel);
      }

      _initialized = true;
      debugPrint('CookTimerNotificationService initialized');
    } catch (e) {
      debugPrint('Failed to initialize CookTimerNotificationService: $e');
    }
  }

  /// Schedule a local notification to fire when the timer expires.
  Future<void> scheduleTimerNotification({
    required int id,
    required String label,
    required DateTime expiresAt,
    required String recipeId,
  }) async {
    if (!_initialized) return;

    try {
      final scheduledDate = tz.TZDateTime.from(expiresAt, tz.local);

      const androidDetails = AndroidNotificationDetails(
        _channelId,
        _channelName,
        channelDescription: _channelDesc,
        importance: Importance.max,
        priority: Priority.max,
        fullScreenIntent: false,
        category: AndroidNotificationCategory.alarm,
      );
      const iosDetails = DarwinNotificationDetails(
        interruptionLevel: InterruptionLevel.timeSensitive,
        presentAlert: true,
        presentSound: true,
      );
      const details = NotificationDetails(
        android: androidDetails,
        iOS: iosDetails,
      );

      await _plugin.zonedSchedule(
        id,
        'Timer done',
        label,
        scheduledDate,
        details,
        androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
        payload: recipeId,
      );

      debugPrint('Scheduled timer notification id=$id for $scheduledDate');
    } catch (e) {
      debugPrint('Failed to schedule timer notification: $e');
    }
  }

  /// Cancel a previously scheduled timer notification.
  Future<void> cancelTimerNotification(int id) async {
    try {
      await _plugin.cancel(id);
      debugPrint('Cancelled timer notification id=$id');
    } catch (e) {
      debugPrint('Failed to cancel timer notification id=$id: $e');
    }
  }

  /// Navigate to cook mode for the recipe when the user taps a timer notification.
  void handleNotificationTap(String? payload) {
    if (payload == null || payload.isEmpty) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      appRouter.push('/recipes/$payload/cook');
    });
  }

  void _onNotificationResponse(NotificationResponse response) {
    handleNotificationTap(response.payload);
  }
}
