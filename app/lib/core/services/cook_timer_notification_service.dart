import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_timezone/flutter_timezone.dart';
import 'package:timezone/data/latest_all.dart' as tz;
import 'package:timezone/timezone.dart' as tz;

import '../router/app_router.dart';

/// Top-level background handler: fires when app is killed and user interacts
/// with a timer notification action or tap.
@pragma('vm:entry-point')
void _backgroundNotificationHandler(NotificationResponse response) {
  final actionId = response.actionId;
  final payloadStr = response.payload;
  final payload = _parsePayload(payloadStr);

  if (actionId != null && actionId.isNotEmpty) {
    _handleBackgroundAction(actionId, payload);
    return;
  }

  // Default tap — open cook mode
  final recipeId = payload['recipe_id'] as String?;
  if (recipeId != null && recipeId.isNotEmpty) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      appRouter.push('/recipes/$recipeId/cook');
    });
  }
}

/// Handle notification actions that don't need the full UI (background).
void _handleBackgroundAction(String actionId, Map<String, dynamic> payload) {
  final plugin = FlutterLocalNotificationsPlugin();
  switch (actionId) {
    case 'TIMER_ADD_2_MIN':
    case 'TIMER_ADD_5_MIN':
      final minutes = actionId == 'TIMER_ADD_2_MIN' ? 2 : 5;
      final label = payload['timer_label'] as String? ?? 'Timer';
      final recipeId = payload['recipe_id'] as String? ?? '';
      final originalDuration = payload['original_duration_seconds'] as int? ?? 0;
      final newPayload = {
        ...payload,
        'timer_label': label,
      };
      _scheduleNotification(
        plugin,
        label: '$label (+${minutes}m)',
        delay: Duration(minutes: minutes),
        payload: newPayload,
        recipeId: recipeId,
        originalDuration: originalDuration,
      );
    case 'TIMER_RESET':
      final duration = payload['original_duration_seconds'] as int? ?? 0;
      if (duration > 0) {
        final label = payload['timer_label'] as String? ?? 'Timer';
        final recipeId = payload['recipe_id'] as String? ?? '';
        _scheduleNotification(
          plugin,
          label: '$label (reset)',
          delay: Duration(seconds: duration),
          payload: payload,
          recipeId: recipeId,
          originalDuration: duration,
        );
      }
    case 'MEAL_SNOOZE_15':
      final title = payload['meal_title'] as String? ?? 'Meal Reminder';
      final recipeId = payload['recipe_id'] as String? ?? '';
      _scheduleNotification(
        plugin,
        label: title,
        delay: const Duration(minutes: 15),
        payload: payload,
        recipeId: recipeId,
        categoryId: 'meal_reminder',
      );
    case 'TIMER_DISMISS':
      break; // Just dismiss — no action needed
  }
}

Future<void> _scheduleNotification(
  FlutterLocalNotificationsPlugin plugin, {
  required String label,
  required Duration delay,
  required Map<String, dynamic> payload,
  required String recipeId,
  int originalDuration = 0,
  String categoryId = 'cooking_timer',
}) async {
  try {
    tz.initializeTimeZones();
    final timezoneName = await FlutterTimezone.getLocalTimezone();
    tz.setLocalLocation(tz.getLocation(timezoneName));

    final scheduledDate = tz.TZDateTime.now(tz.local).add(delay);
    final id = DateTime.now().millisecondsSinceEpoch % 100000;

    final androidDetails = AndroidNotificationDetails(
      _channelId,
      _channelName,
      channelDescription: _channelDesc,
      importance: Importance.max,
      priority: Priority.max,
      category: AndroidNotificationCategory.alarm,
      groupKey: 'cooking_timer',
      actions: categoryId == 'cooking_timer' ? timerAndroidActions : null,
    );
    final iosDetails = DarwinNotificationDetails(
      interruptionLevel: InterruptionLevel.timeSensitive,
      presentAlert: true,
      presentSound: true,
      categoryIdentifier: categoryId,
      threadIdentifier: 'cooking_timer',
    );
    final details = NotificationDetails(android: androidDetails, iOS: iosDetails);

    await plugin.zonedSchedule(
      id,
      'Timer done',
      label,
      scheduledDate,
      details,
      androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
      uiLocalNotificationDateInterpretation:
          UILocalNotificationDateInterpretation.absoluteTime,
      payload: jsonEncode(payload),
    );
  } catch (e) {
    debugPrint('Failed to schedule notification from background: $e');
  }
}

Map<String, dynamic> _parsePayload(String? payloadStr) {
  if (payloadStr == null || payloadStr.isEmpty) return {};
  try {
    return jsonDecode(payloadStr) as Map<String, dynamic>;
  } catch (_) {
    // Legacy: plain recipeId string
    return {'recipe_id': payloadStr};
  }
}

const _channelId = 'cook_timers';
const _channelName = 'Cooking Timers';
const _channelDesc = 'Alerts when a cooking timer finishes';

/// Android inline actions attached to every cook-timer notification.
/// Action IDs match the iOS `DarwinNotificationCategory` registration
/// so the shared `_backgroundNotificationHandler` routes taps
/// identically on both platforms. Exposed (no leading underscore) so
/// unit tests can assert the shipped list shape.
const timerAndroidActions = <AndroidNotificationAction>[
  AndroidNotificationAction('TIMER_ADD_2_MIN', '+ 2 min',
      showsUserInterface: false),
  AndroidNotificationAction('TIMER_ADD_5_MIN', '+ 5 min',
      showsUserInterface: false),
  AndroidNotificationAction('TIMER_RESET', 'Reset',
      showsUserInterface: false),
  AndroidNotificationAction('TIMER_DISMISS', 'Stop',
      showsUserInterface: false),
];

/// Notification categories for iOS action buttons.
final _cookingTimerCategory = DarwinNotificationCategory(
  'cooking_timer',
  actions: [
    DarwinNotificationAction.plain('TIMER_ADD_2_MIN', 'Add 2 Minutes'),
    DarwinNotificationAction.plain('TIMER_ADD_5_MIN', 'Add 5 Minutes'),
    DarwinNotificationAction.plain('TIMER_RESET', 'Reset Timer'),
    DarwinNotificationAction.plain('TIMER_DISMISS', 'Dismiss',
        options: {DarwinNotificationActionOption.destructive}),
  ],
);

final _mealReminderCategory = DarwinNotificationCategory(
  'meal_reminder',
  actions: [
    DarwinNotificationAction.plain(
      'MEAL_START_COOKING',
      'Start Cooking',
      options: {DarwinNotificationActionOption.foreground},
    ),
    DarwinNotificationAction.plain(
      'MEAL_VIEW_RECIPE',
      'View Recipe',
      options: {DarwinNotificationActionOption.foreground},
    ),
    DarwinNotificationAction.plain('MEAL_SNOOZE_15', 'Snooze 15 min'),
  ],
);

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
      final iosInit = DarwinInitializationSettings(
        requestAlertPermission: false,
        requestBadgePermission: false,
        requestSoundPermission: false,
        notificationCategories: [
          _cookingTimerCategory,
          _mealReminderCategory,
        ],
      );
      final initSettings = InitializationSettings(
        android: androidInit,
        iOS: iosInit,
      );

      await _plugin.initialize(
        initSettings,
        onDidReceiveNotificationResponse: _onNotificationResponse,
        onDidReceiveBackgroundNotificationResponse:
            _backgroundNotificationHandler,
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
    int? stepIndex,
    int? originalDurationSeconds,
  }) async {
    if (!_initialized) return;

    try {
      final scheduledDate = tz.TZDateTime.from(expiresAt, tz.local);

      // Calculate original duration if not provided
      final durationSecs = originalDurationSeconds ??
          expiresAt.difference(DateTime.now()).inSeconds;

      final payload = jsonEncode({
        'recipe_id': recipeId,
        'timer_label': label,
        'original_duration_seconds': durationSecs,
        if (stepIndex != null) 'step_index': stepIndex,
      });

      final androidDetails = AndroidNotificationDetails(
        _channelId,
        _channelName,
        channelDescription: _channelDesc,
        importance: Importance.max,
        priority: Priority.max,
        fullScreenIntent: false,
        category: AndroidNotificationCategory.alarm,
        groupKey: 'cooking_timer',
        actions: timerAndroidActions,
      );
      const iosDetails = DarwinNotificationDetails(
        interruptionLevel: InterruptionLevel.timeSensitive,
        presentAlert: true,
        presentSound: true,
        categoryIdentifier: 'cooking_timer',
        threadIdentifier: 'cooking_timer',
      );
      final details = NotificationDetails(
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
        uiLocalNotificationDateInterpretation:
            UILocalNotificationDateInterpretation.absoluteTime,
        payload: payload,
      );

      debugPrint('Scheduled timer notification id=$id for $scheduledDate');
    } catch (e) {
      debugPrint('Failed to schedule timer notification: $e');
    }
  }

  /// Schedule a meal reminder notification.
  Future<void> scheduleMealReminder({
    required int id,
    required String title,
    required String body,
    required DateTime scheduledAt,
    required String recipeId,
  }) async {
    if (!_initialized) return;

    try {
      final scheduledDate = tz.TZDateTime.from(scheduledAt, tz.local);

      final payload = jsonEncode({
        'recipe_id': recipeId,
        'meal_title': title,
      });

      const androidDetails = AndroidNotificationDetails(
        _channelId,
        _channelName,
        channelDescription: _channelDesc,
        importance: Importance.high,
        priority: Priority.high,
      );
      const iosDetails = DarwinNotificationDetails(
        presentAlert: true,
        presentSound: true,
        categoryIdentifier: 'meal_reminder',
        threadIdentifier: 'meal_reminder',
      );
      const details = NotificationDetails(
        android: androidDetails,
        iOS: iosDetails,
      );

      await _plugin.zonedSchedule(
        id,
        title,
        body,
        scheduledDate,
        details,
        androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
        uiLocalNotificationDateInterpretation:
            UILocalNotificationDateInterpretation.absoluteTime,
        payload: payload,
      );
    } catch (e) {
      debugPrint('Failed to schedule meal reminder: $e');
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

  /// Handle notification tap — navigate to appropriate screen.
  void handleNotificationTap(String? payloadStr) {
    final payload = _parsePayload(payloadStr);
    final recipeId = payload['recipe_id'] as String?;
    if (recipeId == null || recipeId.isEmpty) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      appRouter.push('/recipes/$recipeId/cook');
    });
  }

  void _onNotificationResponse(NotificationResponse response) {
    final actionId = response.actionId;
    final payload = _parsePayload(response.payload);

    if (actionId == null || actionId.isEmpty) {
      // Default tap
      handleNotificationTap(response.payload);
      return;
    }

    // Foreground actions
    switch (actionId) {
      case 'MEAL_START_COOKING':
        final recipeId = payload['recipe_id'] as String?;
        if (recipeId != null) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            appRouter.push('/recipes/$recipeId/cook');
          });
        }
      case 'MEAL_VIEW_RECIPE':
        final recipeId = payload['recipe_id'] as String?;
        if (recipeId != null) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            appRouter.push('/recipes/$recipeId');
          });
        }
      default:
        // Background actions (add time, snooze, reset, dismiss)
        // are handled by _backgroundNotificationHandler
        _handleBackgroundAction(actionId, payload);
    }
  }
}
