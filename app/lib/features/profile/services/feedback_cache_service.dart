import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Offline queue for outbound feedback submissions.
///
/// Each queued entry is persisted to SharedPreferences under
/// `palateful_pending_feedback` as a JSON-encoded list. The shape matches
/// what `POST /v1/users/me/feedback` expects plus a `queued_at` timestamp
/// for future debugging. On a successful flush the key is cleared.
///
/// Mirrors the `RecipeCacheService.queueNoteAdd` / `clearPendingNotes`
/// pattern — same storage, same prefix convention, same "best effort;
/// log and swallow" error stance so a crash in the cache layer never
/// breaks the caller UX.
class FeedbackCacheService {
  static const _pendingFeedbackKey = 'palateful_pending_feedback';

  /// Append a feedback draft to the pending-flush queue.
  Future<void> queueFeedback({
    required String body,
    String? category,
    Map<String, dynamic>? context,
  }) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final existing = prefs.getString(_pendingFeedbackKey);
      final List<dynamic> queue =
          existing != null ? jsonDecode(existing) as List<dynamic> : [];
      queue.add({
        'body': body,
        if (category != null) 'category': category,
        if (context != null) 'context': context,
        'queued_at': DateTime.now().toIso8601String(),
      });
      await prefs.setString(_pendingFeedbackKey, jsonEncode(queue));
    } catch (e) {
      debugPrint('FeedbackCacheService: failed to queue feedback: $e');
    }
  }

  /// Return every queued feedback entry (FIFO). Each map preserves the
  /// keys set by [queueFeedback] (body, optional category, optional
  /// context, queued_at).
  Future<List<Map<String, dynamic>>> getPendingFeedback() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_pendingFeedbackKey);
      if (raw == null) return [];
      final list = jsonDecode(raw) as List<dynamic>;
      return list.cast<Map<String, dynamic>>();
    } catch (e) {
      debugPrint('FeedbackCacheService: failed to read queue: $e');
      return [];
    }
  }

  /// Drop every entry from the queue. Called after a successful flush.
  Future<void> clearPendingFeedback() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_pendingFeedbackKey);
    } catch (e) {
      debugPrint('FeedbackCacheService: failed to clear queue: $e');
    }
  }

  /// True when there's at least one queued entry. Used by the profile
  /// screen's lifecycle observer to short-circuit the flush when there's
  /// nothing to send.
  Future<bool> hasPending() async {
    final items = await getPendingFeedback();
    return items.isNotEmpty;
  }
}
