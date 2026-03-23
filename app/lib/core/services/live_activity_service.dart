import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:live_activities/live_activities.dart';

/// Service for managing iOS Live Activities (Dynamic Island + Lock Screen).
class LiveActivityService {
  final LiveActivities _liveActivities = LiveActivities();
  final Map<int, String> _timerActivityIds = {};
  bool _initialized = false;

  /// Initialize the Live Activities plugin.
  Future<void> initialize() async {
    if (_initialized || !Platform.isIOS) return;
    try {
      await _liveActivities.init(appGroupId: 'group.com.palateful.app');
      _initialized = true;
      debugPrint('LiveActivityService initialized');
    } catch (e) {
      debugPrint('Failed to initialize LiveActivityService: $e');
    }
  }

  /// Start a Live Activity for a cooking timer.
  ///
  /// Returns the activity ID for later updates/cancellation.
  Future<String?> startTimerActivity({
    required int notifId,
    required String timerLabel,
    required String recipeName,
    required Duration duration,
  }) async {
    if (!_initialized) return null;

    try {
      final endTime = DateTime.now().add(duration);
      final activityId = await _liveActivities.createActivity({
        'timerLabel': timerLabel,
        'recipeName': recipeName,
        'originalDuration': duration.inSeconds.toDouble(),
        'endTime': endTime.millisecondsSinceEpoch.toDouble(),
        'isComplete': false,
      });

      if (activityId != null) {
        _timerActivityIds[notifId] = activityId;
        debugPrint('Started Live Activity $activityId for timer $notifId');
      }
      return activityId;
    } catch (e) {
      debugPrint('Failed to start Live Activity: $e');
      return null;
    }
  }

  /// Update a timer Live Activity (e.g., when adding time).
  Future<void> updateTimerActivity({
    required int notifId,
    required Duration newRemaining,
  }) async {
    if (!_initialized) return;
    final activityId = _timerActivityIds[notifId];
    if (activityId == null) return;

    try {
      final newEndTime = DateTime.now().add(newRemaining);
      await _liveActivities.updateActivity(activityId, {
        'endTime': newEndTime.millisecondsSinceEpoch.toDouble(),
        'isComplete': false,
      });
    } catch (e) {
      debugPrint('Failed to update Live Activity: $e');
    }
  }

  /// Mark a timer Live Activity as complete.
  Future<void> completeTimerActivity(int notifId) async {
    if (!_initialized) return;
    final activityId = _timerActivityIds[notifId];
    if (activityId == null) return;

    try {
      await _liveActivities.updateActivity(activityId, {
        'isComplete': true,
      });
      // Auto-dismiss after 5 minutes
      Future.delayed(const Duration(minutes: 5), () {
        endTimerActivity(notifId);
      });
    } catch (e) {
      debugPrint('Failed to complete Live Activity: $e');
    }
  }

  /// End and remove a timer Live Activity.
  Future<void> endTimerActivity(int notifId) async {
    if (!_initialized) return;
    final activityId = _timerActivityIds.remove(notifId);
    if (activityId == null) return;

    try {
      await _liveActivities.endActivity(activityId);
    } catch (e) {
      debugPrint('Failed to end Live Activity: $e');
    }
  }

  /// End all active Live Activities.
  Future<void> endAll() async {
    if (!_initialized) return;
    try {
      await _liveActivities.endAllActivities();
      _timerActivityIds.clear();
    } catch (e) {
      debugPrint('Failed to end all Live Activities: $e');
    }
  }
}
