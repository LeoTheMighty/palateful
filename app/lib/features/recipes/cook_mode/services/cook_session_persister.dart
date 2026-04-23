import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../../core/services/error_reporter.dart';
import '../shared/cook_plan.dart';

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
///
/// `sourceRecipeId` (cmmrf-2) tags meal-mode timers with the recipe
/// that owned them when they were started. Null on recipe-mode AND on
/// v1-restored meal-mode timers; meal UI treats null as "no prefix"
/// (active-timers chip + completion snackbar both fall back to the
/// prefixless copy — honesty over guessing).
@immutable
class SavedTimerState {
  final String label;
  final int deadlineMs;
  final int totalDurationSeconds;
  final String source;
  final String? sourceRecipeId;

  const SavedTimerState({
    required this.label,
    required this.deadlineMs,
    required this.totalDurationSeconds,
    required this.source,
    this.sourceRecipeId,
  });

  Map<String, dynamic> toJson() => {
        'label': label,
        'deadline_ms': deadlineMs,
        'total_duration_s': totalDurationSeconds,
        'source': source,
        if (sourceRecipeId != null) 'source_recipe_id': sourceRecipeId,
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
    final rawSource = raw['source_recipe_id'];
    final sourceRecipeId = rawSource is String ? rawSource : null;
    return SavedTimerState(
      label: label,
      deadlineMs: deadline,
      totalDurationSeconds: duration,
      source: source,
      sourceRecipeId: sourceRecipeId,
    );
  }

  @override
  bool operator ==(Object other) =>
      other is SavedTimerState &&
      other.label == label &&
      other.deadlineMs == deadlineMs &&
      other.totalDurationSeconds == totalDurationSeconds &&
      other.source == source &&
      other.sourceRecipeId == sourceRecipeId;

  @override
  int get hashCode =>
      Object.hash(label, deadlineMs, totalDurationSeconds, source, sourceRecipeId);
}

/// Serialized cook-mode state for one recipe (or one meal).
///
/// cmmrf-2 — schema v2 moves to per-recipe maps keyed by `recipe_id`.
/// Meal-mode surfaces `activeRecipeId` + the full step/completed maps.
/// Recipe-mode sets `activeRecipeId = null` and keeps the maps
/// single-keyed under `targetId`.
///
/// ### Migration invariant
///
/// After [fromJson] returns a non-null state, exactly one of the
/// following holds:
///
///  * `legacyCurrentStep == null && legacyCompletedSteps == null` —
///    state is fully in v2 shape. `currentStepByRecipe` +
///    `completedStepsByRecipe` are authoritative. Recipe-mode v1
///    payloads land here via the self-contained unpack (no plan
///    needed). v2-native payloads land here directly.
///
///  * `legacyCurrentStep != null && legacyCompletedSteps != null &&
///    currentStepByRecipe.isEmpty && completedStepsByRecipe.isEmpty &&
///    targetKind == CookTargetKind.meal` — **transitional meal-v1**.
///    The persister couldn't unpack flat → per-recipe without the
///    plan. Callers must invoke [unpackLegacyMeal] once the plan
///    lands before using the state.
///
/// No other combination is valid.
@immutable
class CookSessionState {
  static const int currentSchemaVersion = 2;

  final CookTargetKind targetKind;
  final String targetId;
  final int startedAtMs;
  final int cumulativeElapsedMs;

  /// Pointer to the currently-active recipe id. Null on recipe-mode
  /// (targetId is the implicit active recipe); non-null on meal-mode.
  final String? activeRecipeId;

  /// Per-recipe current step index. Keys are recipe ids; values are
  /// 0-indexed local step indices.
  final Map<String, int> currentStepByRecipe;

  /// Per-recipe completed step indices (local, not flat). Keys are
  /// recipe ids; values are sets of 0-indexed local step indices.
  final Map<String, Set<int>> completedStepsByRecipe;

  final List<String> checkedIngredients;
  final List<SavedTimerState> activeTimers;
  final int updatedAtMs;

  /// Transient migration fields — non-null ONLY in the transitional
  /// meal-v1 state (invariant case b). Never serialized.
  final int? legacyCurrentStep;
  final Set<int>? legacyCompletedSteps;

  const CookSessionState({
    required this.targetKind,
    required this.targetId,
    required this.startedAtMs,
    required this.cumulativeElapsedMs,
    this.activeRecipeId,
    required this.currentStepByRecipe,
    required this.completedStepsByRecipe,
    required this.checkedIngredients,
    required this.activeTimers,
    required this.updatedAtMs,
    this.legacyCurrentStep,
    this.legacyCompletedSteps,
  });

  /// True when this state is in the transitional meal-v1 shape and
  /// needs [unpackLegacyMeal] before use.
  bool get isTransitionalMealLegacy =>
      legacyCurrentStep != null &&
      legacyCompletedSteps != null &&
      currentStepByRecipe.isEmpty &&
      completedStepsByRecipe.isEmpty &&
      targetKind == CookTargetKind.meal;

  Map<String, dynamic> toJson() => {
        'schema_version': currentSchemaVersion,
        'target_kind': targetKind.wireName,
        'target_id': targetId,
        'started_at_ms': startedAtMs,
        'cumulative_elapsed_ms': cumulativeElapsedMs,
        if (activeRecipeId != null) 'active_recipe_id': activeRecipeId,
        'current_step_by_recipe': currentStepByRecipe,
        'completed_steps_by_recipe': {
          for (final e in completedStepsByRecipe.entries)
            e.key: (e.value.toList()..sort()),
        },
        'checked_ingredients': checkedIngredients,
        'active_timers': activeTimers.map((t) => t.toJson()).toList(),
        'updated_at_ms': updatedAtMs,
      };

  /// Returns null when the payload is unparseable OR the schema
  /// version is unknown. Schema v1 (previous shape) is migrated in
  /// place — recipe-mode payloads are fully unpacked; meal-mode
  /// payloads are marked transitional and await [unpackLegacyMeal].
  static CookSessionState? fromJson(dynamic raw) {
    if (raw is! Map) return null;
    final version = raw['schema_version'];
    if (version is! int) return null;
    if (version != 1 && version != currentSchemaVersion) return null;
    final targetKind = CookTargetKind.fromWire(raw['target_kind'] as String?);
    if (targetKind == null) return null;
    final targetId = raw['target_id'];
    if (targetId is! String) return null;
    final startedAt = _readInt(raw['started_at_ms']);
    final elapsed = _readInt(raw['cumulative_elapsed_ms']);
    final updatedAt = _readInt(raw['updated_at_ms']);
    if (startedAt == null || elapsed == null || updatedAt == null) {
      return null;
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

    if (version == 1) {
      final legacyCurrent = _readInt(raw['current_step']);
      if (legacyCurrent == null) return null;
      final legacyCompleted = <int>{};
      final rawCompleted = raw['completed_steps'];
      if (rawCompleted is List) {
        for (final entry in rawCompleted) {
          final parsed = _readInt(entry);
          if (parsed != null) legacyCompleted.add(parsed);
        }
      }
      if (targetKind == CookTargetKind.recipe) {
        // Self-contained unpack — single recipe's flat step *is* its
        // local step; no plan needed.
        return CookSessionState(
          targetKind: CookTargetKind.recipe,
          targetId: targetId,
          startedAtMs: startedAt,
          cumulativeElapsedMs: elapsed,
          activeRecipeId: null,
          currentStepByRecipe: {targetId: legacyCurrent},
          completedStepsByRecipe: {targetId: legacyCompleted},
          checkedIngredients: checked,
          activeTimers: timers,
          updatedAtMs: updatedAt,
        );
      }
      // Meal-mode v1 — transitional shape; callers unpack via
      // [unpackLegacyMeal] once the plan is loaded.
      return CookSessionState(
        targetKind: CookTargetKind.meal,
        targetId: targetId,
        startedAtMs: startedAt,
        cumulativeElapsedMs: elapsed,
        activeRecipeId: null,
        currentStepByRecipe: const {},
        completedStepsByRecipe: const {},
        checkedIngredients: checked,
        activeTimers: timers,
        updatedAtMs: updatedAt,
        legacyCurrentStep: legacyCurrent,
        legacyCompletedSteps: legacyCompleted,
      );
    }

    // v2 native deserialization.
    final activeRecipeId = raw['active_recipe_id'];
    final currentMap = <String, int>{};
    final rawCurrent = raw['current_step_by_recipe'];
    if (rawCurrent is Map) {
      rawCurrent.forEach((k, v) {
        if (k is String) {
          final parsed = _readInt(v);
          if (parsed != null) currentMap[k] = parsed;
        }
      });
    }
    final completedMap = <String, Set<int>>{};
    final rawCompletedMap = raw['completed_steps_by_recipe'];
    if (rawCompletedMap is Map) {
      rawCompletedMap.forEach((k, v) {
        if (k is String && v is List) {
          final parsed = <int>{};
          for (final entry in v) {
            final n = _readInt(entry);
            if (n != null) parsed.add(n);
          }
          completedMap[k] = parsed;
        }
      });
    }
    return CookSessionState(
      targetKind: targetKind,
      targetId: targetId,
      startedAtMs: startedAt,
      cumulativeElapsedMs: elapsed,
      activeRecipeId: activeRecipeId is String ? activeRecipeId : null,
      currentStepByRecipe: currentMap,
      completedStepsByRecipe: completedMap,
      checkedIngredients: checked,
      activeTimers: timers,
      updatedAtMs: updatedAt,
    );
  }

  /// Unpack a transitional meal-v1 state (invariant case b) into the
  /// v2 per-recipe shape using [plan]. No-op when the state is
  /// already in case (a) — safe to call unconditionally.
  CookSessionState unpackLegacyMeal(CookPlan plan) {
    if (!isTransitionalMealLegacy) return this;
    final flatCurrent = legacyCurrentStep!;
    final flatCompleted = legacyCompletedSteps!;
    final clampedCurrent = plan.totalSteps == 0
        ? 0
        : flatCurrent.clamp(0, plan.totalSteps - 1);
    final atCurrent = plan.stepAt(clampedCurrent);
    final activeId = plan.components[atCurrent.componentIndex].recipeId;
    final currentMap = <String, int>{
      for (final c in plan.components) c.recipeId: 0,
    };
    currentMap[activeId] = atCurrent.stepIndex;
    final completedMap = <String, Set<int>>{
      for (final c in plan.components) c.recipeId: <int>{},
    };
    for (final flat in flatCompleted) {
      if (flat < 0 || flat >= plan.totalSteps) continue;
      final at = plan.stepAt(flat);
      final id = plan.components[at.componentIndex].recipeId;
      completedMap[id]!.add(at.stepIndex);
    }
    return CookSessionState(
      targetKind: targetKind,
      targetId: targetId,
      startedAtMs: startedAtMs,
      cumulativeElapsedMs: cumulativeElapsedMs,
      activeRecipeId: activeId,
      currentStepByRecipe: currentMap,
      completedStepsByRecipe: completedMap,
      checkedIngredients: checkedIngredients,
      activeTimers: activeTimers,
      updatedAtMs: updatedAtMs,
    );
  }

  CookSessionState copyWith({
    CookTargetKind? targetKind,
    String? targetId,
    int? startedAtMs,
    int? cumulativeElapsedMs,
    String? activeRecipeId,
    Map<String, int>? currentStepByRecipe,
    Map<String, Set<int>>? completedStepsByRecipe,
    List<String>? checkedIngredients,
    List<SavedTimerState>? activeTimers,
    int? updatedAtMs,
  }) {
    return CookSessionState(
      targetKind: targetKind ?? this.targetKind,
      targetId: targetId ?? this.targetId,
      startedAtMs: startedAtMs ?? this.startedAtMs,
      cumulativeElapsedMs: cumulativeElapsedMs ?? this.cumulativeElapsedMs,
      activeRecipeId: activeRecipeId ?? this.activeRecipeId,
      currentStepByRecipe: currentStepByRecipe ?? this.currentStepByRecipe,
      completedStepsByRecipe:
          completedStepsByRecipe ?? this.completedStepsByRecipe,
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
        // Unknown schema version — don't clear (might be a forward-
        // compat newer build's data); just skip.
        if (decoded is Map && decoded['schema_version'] is int) {
          final v = decoded['schema_version'] as int;
          if (v != 1 && v != CookSessionState.currentSchemaVersion) {
            return null;
          }
        }
        // Structurally invalid under a known schema — treat as
        // malformed.
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
