import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Service for caching recipe data locally and queuing offline note additions.
///
/// Keys use the `palateful_` prefix to avoid collisions with other packages:
/// - `palateful_recipe_{recipeId}`    — cached recipe JSON
/// - `palateful_pending_notes`        — JSON-encoded list of pending note additions
/// - `palateful_cook_logs_{recipeId}` — JSON-encoded list of cook log entries
class RecipeCacheService {
  static const _recipeKeyPrefix = 'palateful_recipe_';
  static const _pendingNotesKey = 'palateful_pending_notes';
  static const _cookLogsKeyPrefix = 'palateful_cook_logs_';

  /// Serializes [data] to JSON and stores it under `palateful_recipe_[recipeId]`.
  Future<void> cacheRecipe(String recipeId, Map<String, dynamic> data) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_recipeKeyPrefix + recipeId, jsonEncode(data));
    } catch (e) {
      debugPrint('RecipeCacheService: failed to cache recipe $recipeId: $e');
    }
  }

  /// Returns the cached recipe data for [recipeId], or null if not cached.
  Future<Map<String, dynamic>?> loadCachedRecipe(String recipeId) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_recipeKeyPrefix + recipeId);
      if (raw == null) return null;
      return jsonDecode(raw) as Map<String, dynamic>;
    } catch (e) {
      debugPrint('RecipeCacheService: failed to load cached recipe $recipeId: $e');
      return null;
    }
  }

  /// Returns true if a cached entry exists for [recipeId].
  Future<bool> hasCachedRecipe(String recipeId) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return prefs.containsKey(_recipeKeyPrefix + recipeId);
    } catch (e) {
      return false;
    }
  }

  /// Appends a pending note to the queue for later sync.
  ///
  /// Stored as `{recipe_id, body, queued_at}` in a JSON list under
  /// [_pendingNotesKey].
  Future<void> queueNoteAdd(String recipeId, String body) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final existing = prefs.getString(_pendingNotesKey);
      final List<dynamic> notes =
          existing != null ? jsonDecode(existing) as List<dynamic> : [];
      notes.add({
        'recipe_id': recipeId,
        'body': body,
        'queued_at': DateTime.now().toIso8601String(),
      });
      await prefs.setString(_pendingNotesKey, jsonEncode(notes));
    } catch (e) {
      debugPrint('RecipeCacheService: failed to queue note: $e');
    }
  }

  /// Returns all pending (queued) note additions.
  Future<List<Map<String, dynamic>>> getPendingNotes() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_pendingNotesKey);
      if (raw == null) return [];
      final list = jsonDecode(raw) as List<dynamic>;
      return list.cast<Map<String, dynamic>>();
    } catch (e) {
      debugPrint('RecipeCacheService: failed to get pending notes: $e');
      return [];
    }
  }

  /// Removes all pending notes (call after successful sync).
  Future<void> clearPendingNotes() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_pendingNotesKey);
    } catch (e) {
      debugPrint('RecipeCacheService: failed to clear pending notes: $e');
    }
  }

  /// Records a cook session for [recipeId] with the given [rating] (1–5) and
  /// timestamp. Stored under `palateful_cook_logs_{recipeId}`.
  Future<void> logCook(String recipeId, int rating, DateTime cookedAt) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final key = _cookLogsKeyPrefix + recipeId;
      final existing = prefs.getString(key);
      final List<dynamic> logs =
          existing != null ? jsonDecode(existing) as List<dynamic> : [];
      logs.add({
        'recipe_id': recipeId,
        'rating': rating,
        'cooked_at': cookedAt.toIso8601String(),
      });
      await prefs.setString(key, jsonEncode(logs));
    } catch (e) {
      debugPrint('RecipeCacheService: failed to log cook $recipeId: $e');
    }
  }

  /// Returns all cook log entries for [recipeId], ordered oldest-first.
  Future<List<Map<String, dynamic>>> getCookLogs(String recipeId) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_cookLogsKeyPrefix + recipeId);
      if (raw == null) return [];
      final list = jsonDecode(raw) as List<dynamic>;
      return list.cast<Map<String, dynamic>>();
    } catch (e) {
      debugPrint('RecipeCacheService: failed to get cook logs $recipeId: $e');
      return [];
    }
  }
}
