import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../../core/services/error_reporter.dart';

/// Identifies the kind of target a cook session is attached to. Recipe
/// cook uses `recipe`; meal cook (downstream — `epic-cook-mode-meal`)
/// uses `meal`.
enum CookTargetKind {
  recipe,
  meal;

  String get wireName => switch (this) {
        CookTargetKind.recipe => 'recipe',
        CookTargetKind.meal => 'meal',
      };

  static CookTargetKind? fromWire(String? name) {
    switch (name) {
      case 'recipe':
        return CookTargetKind.recipe;
      case 'meal':
        return CookTargetKind.meal;
      default:
        return null;
    }
  }
}

/// Canonical key format for [CookSessionPersister].
///
/// Keys are the only coupling between the persister and its callers;
/// hiding the format behind helpers means future changes (namespace
/// prefix, sharded storage, …) stay local.
class CookSessionKey {
  const CookSessionKey._();

  static const String prefix = 'cook_session_';
  static const String recipePrefix = '${prefix}recipe_';
  static const String mealPrefix = '${prefix}meal_';

  static String forRecipe(String recipeId) => '$recipePrefix$recipeId';
  static String forMeal(String mealId) => '$mealPrefix$mealId';
}

/// A single saved cook-mode timer. Stores absolute `deadline_ms` (epoch
/// milliseconds) so remaining time survives sleep / wake / clock
/// adjustments.
@immutable
class SavedTimerState {
  final String label;
  final int deadlineMs;
  final int totalDurationSeconds;
  final String source;

  const SavedTimerState({
    required this.label,
    required this.deadlineMs,
    required this.totalDurationSeconds,
    required this.source,
  });

  Map<String, dynamic> toJson() => {
        'label': label,
        'deadline_ms': deadlineMs,
        'total_duration_s': totalDurationSeconds,
        'source': source,
      };

  static SavedTimerState? fromJson(dynamic raw) {
    if (raw is! Map) return null;
    final label = raw['label'];
    final deadline = raw['deadline_ms'];
    final duration = raw['total_duration_s'];
    final source = raw['source'];
    if (label is! String || deadline is! int || duration is! int || source is! String) {
      return null;
    }
    return SavedTimerState(
      label: label,
      deadlineMs: deadline,
      totalDurationSeconds: duration,
      source: source,
    );
  }

  @override
  bool operator ==(Object other) =>
      other is SavedTimerState &&
      other.label == label &&
      other.deadlineMs == deadlineMs &&
      other.totalDurationSeconds == totalDurationSeconds &&
      other.source == source;

  @override
  int get hashCode => Object.hash(label, deadlineMs, totalDurationSeconds, source);
}

/// Serialized cook-mode state for one recipe (or one meal).
///
/// Schema is forward-compatible: reading an unknown `schema_version`
/// returns null from [CookSessionPersister.load]. Never migrate old
/// state in place — let the user re-enter a fresh session.
@immutable
class CookSessionState {
  static const int currentSchemaVersion = 1;

  final CookTargetKind targetKind;
  final String targetId;
  final int startedAtMs;
  final int cumulativeElapsedMs;
  final int currentStep;
  final List<int> completedSteps;
  final List<String> checkedIngredients;
  final List<SavedTimerState> activeTimers;
  final int updatedAtMs;

  const CookSessionState({
    required this.targetKind,
    required this.targetId,
    required this.startedAtMs,
    required this.cumulativeElapsedMs,
    required this.currentStep,
    required this.completedSteps,
    required this.checkedIngredients,
    required this.activeTimers,
    required this.updatedAtMs,
  });

  Map<String, dynamic> toJson() => {
        'schema_version': currentSchemaVersion,
        'target_kind': targetKind.wireName,
        'target_id': targetId,
        'started_at_ms': startedAtMs,
        'cumulative_elapsed_ms': cumulativeElapsedMs,
        'current_step': currentStep,
        'completed_steps': completedSteps,
        'checked_ingredients': checkedIngredients,
        'active_timers': activeTimers.map((t) => t.toJson()).toList(),
        'updated_at_ms': updatedAtMs,
      };

  /// Returns null when the payload is unparseable OR the schema version
  /// is unknown. Callers treat null as "no usable state" and the
  /// persister's [CookSessionPersister.load] clears the key.
  static CookSessionState? fromJson(dynamic raw) {
    if (raw is! Map) return null;
    final version = raw['schema_version'];
    if (version != currentSchemaVersion) return null;
    final targetKind = CookTargetKind.fromWire(raw['target_kind'] as String?);
    if (targetKind == null) return null;
    final targetId = raw['target_id'];
    if (targetId is! String) return null;
    final startedAt = _readInt(raw['started_at_ms']);
    final elapsed = _readInt(raw['cumulative_elapsed_ms']);
    final currentStep = _readInt(raw['current_step']);
    final updatedAt = _readInt(raw['updated_at_ms']);
    if (startedAt == null || elapsed == null || currentStep == null || updatedAt == null) {
      return null;
    }
    final completed = <int>[];
    final rawCompleted = raw['completed_steps'];
    if (rawCompleted is List) {
      for (final entry in rawCompleted) {
        final parsed = _readInt(entry);
        if (parsed != null) completed.add(parsed);
      }
    }
    final checked = <String>[];
    final rawChecked = raw['checked_ingredients'];
    if (rawChecked is List) {
      for (final entry in rawChecked) {
        if (entry is String) checked.add(entry);
      }
    }
    final timers = <SavedTimerState>[];
    final rawTimers = raw['active_timers'];
    if (rawTimers is List) {
      for (final entry in rawTimers) {
        final parsed = SavedTimerState.fromJson(entry);
        if (parsed != null) timers.add(parsed);
      }
    }
    return CookSessionState(
      targetKind: targetKind,
      targetId: targetId,
      startedAtMs: startedAt,
      cumulativeElapsedMs: elapsed,
      currentStep: currentStep,
      completedSteps: completed,
      checkedIngredients: checked,
      activeTimers: timers,
      updatedAtMs: updatedAt,
    );
  }

  CookSessionState copyWith({
    CookTargetKind? targetKind,
    String? targetId,
    int? startedAtMs,
    int? cumulativeElapsedMs,
    int? currentStep,
    List<int>? completedSteps,
    List<String>? checkedIngredients,
    List<SavedTimerState>? activeTimers,
    int? updatedAtMs,
  }) {
    return CookSessionState(
      targetKind: targetKind ?? this.targetKind,
      targetId: targetId ?? this.targetId,
      startedAtMs: startedAtMs ?? this.startedAtMs,
      cumulativeElapsedMs: cumulativeElapsedMs ?? this.cumulativeElapsedMs,
      currentStep: currentStep ?? this.currentStep,
      completedSteps: completedSteps ?? this.completedSteps,
      checkedIngredients: checkedIngredients ?? this.checkedIngredients,
      activeTimers: activeTimers ?? this.activeTimers,
      updatedAtMs: updatedAtMs ?? this.updatedAtMs,
    );
  }
}

int? _readInt(dynamic raw) {
  if (raw is int) return raw;
  if (raw is double) return raw.toInt();
  return null;
}

/// Persists cook-mode state to [SharedPreferences].
///
/// Mirrors the pattern used by `core/services/recipe_cache_service.dart`:
/// each method calls `SharedPreferences.getInstance()` inline; no
/// singleton field, no DI registration. Construct a fresh instance at
/// every call site — `CookSessionPersister().load(key)`.
///
/// Values are JSON-encoded [CookSessionState] payloads. Malformed JSON
/// or unknown `schema_version`s are treated as "no state" and the key
/// is cleared so the user isn't stuck at a gate that can't display.
class CookSessionPersister {
  /// Writes larger than this are skipped (with a warning). A realistic
  /// session is ~2 KB; the cap guards against runaway state growth
  /// bloating SharedPreferences.
  static const int maxEncodedBytes = 50 * 1024;

  /// Returns the persisted state under [key], or null when nothing is
  /// stored / the payload is unusable. Side-effect: clears the key when
  /// the payload fails to parse so future reads don't keep paying the
  /// parse cost and the caller's Resume gate doesn't stay stuck.
  Future<CookSessionState?> load(String key) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(key);
    if (raw == null) return null;
    try {
      final decoded = jsonDecode(raw);
      final state = CookSessionState.fromJson(decoded);
      if (state == null) {
        // Unknown schema version or structurally invalid — don't clear
        // (might be a forward-compat newer build's data); just skip.
        if (decoded is Map && decoded['schema_version'] is int &&
            decoded['schema_version'] != CookSessionState.currentSchemaVersion) {
          return null;
        }
        // Structurally invalid under current schema — treat as malformed.
        await prefs.remove(key);
        ErrorReporter.log(
          'CookSessionPersister: cleared malformed state at $key (structure mismatch)',
        );
        return null;
      }
      return state;
    } catch (e) {
      await prefs.remove(key);
      ErrorReporter.log(
        'CookSessionPersister: cleared malformed state at $key ($e)',
      );
      return null;
    }
  }

  /// Writes [state] under [key]. When the JSON payload exceeds
  /// [maxEncodedBytes] the write is skipped (preserves any prior value)
  /// and a warning is logged.
  Future<void> save(String key, CookSessionState state) async {
    final encoded = jsonEncode(state.toJson());
    if (encoded.length > maxEncodedBytes) {
      ErrorReporter.log(
        'CookSessionPersister: state for $key exceeds $maxEncodedBytes '
        'bytes (got ${encoded.length}); skipping save',
      );
      return;
    }
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(key, encoded);
  }

  /// Removes [key]. Idempotent — calling on a missing key is a no-op.
  Future<void> clear(String key) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(key);
  }

  /// Returns every persisted key beginning with [prefix]. Defaults to
  /// the cook-session namespace so callers can enumerate all sessions
  /// without knowing the internal prefix shape.
  Future<List<String>> listKeys({String prefix = CookSessionKey.prefix}) async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getKeys().where((k) => k.startsWith(prefix)).toList();
  }

  /// Scans every cook-session key and deletes ones whose
  /// `updated_at_ms` is older than `now - maxAge`. Malformed payloads
  /// are cleared too (treat as stale). Returns the number of keys
  /// removed. Intended to be called once on app startup — unawaited —
  /// to bound SharedPreferences growth over months of abandoned cooks.
  Future<int> pruneStaleOlderThan(Duration maxAge) async {
    final prefs = await SharedPreferences.getInstance();
    final now = DateTime.now().millisecondsSinceEpoch;
    final cutoff = now - maxAge.inMilliseconds;
    var cleared = 0;
    final keys = prefs.getKeys().where((k) => k.startsWith(CookSessionKey.prefix));
    for (final key in keys) {
      final raw = prefs.getString(key);
      if (raw == null) continue;
      bool remove = false;
      try {
        final decoded = jsonDecode(raw);
        if (decoded is Map && decoded['updated_at_ms'] is int) {
          remove = (decoded['updated_at_ms'] as int) < cutoff;
        } else {
          remove = true;
        }
      } catch (_) {
        remove = true;
      }
      if (remove) {
        await prefs.remove(key);
        cleared++;
      }
    }
    return cleared;
  }
}
