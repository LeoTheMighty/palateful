/// cmm-2 — `MealCookModeScreen` mounts the cook UI for a Meal: parallel
/// load of meal + N component recipes, build a `CookPlan.fromMeal`,
/// and reuse the shared cook widgets (ingredient strip, step navigator,
/// active timers row) to drive the user through every step of every
/// component in section order.
///
/// cmm-3 layers in the section header + navigator boundaries.
/// cmm-4 layers in the source-tagged ingredient strip.
/// cmm-5 layers in component-name timer disambiguation.
/// cmm-6 layers in the multi-row post-cook sheet + early-finish.
/// cmm-7 wires up the persistent-resume + meal-version-drift handling.

library;

import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../../../../core/di/injection.dart';
import '../../../../core/services/api_client.dart';
import '../../../../core/services/cook_timer_notification_service.dart';
import '../../../../core/services/error_reporter.dart';
import '../../../../core/services/live_activity_service.dart';
import '../../../../core/services/recipe_cache_service.dart';
import '../../../../core/theme/theme.dart';
import '../../../meals/models/meal.dart';
import '../../../meals/providers/meals_provider.dart';
import '../services/cook_session_debouncer.dart';
import '../services/cook_session_persister.dart';
import '../shared/cook_plan.dart';
import '../shared/util/timer_regex.dart';
import '../shared/widgets/active_timers_row.dart';
import '../shared/widgets/ingredient_strip.dart';
import '../shared/widgets/manual_timer_sheet.dart';
import '../shared/widgets/post_cook_feedback_sheet.dart';
import '../shared/widgets/step_navigator.dart';
import '../shared/widgets/step_timers_row.dart';
import '../shared/widgets/timer_completion_overlay.dart';
import '../widgets/cook_reset_confirm_sheet.dart';
import '../widgets/cook_resume_gate_sheet.dart';
import 'widgets/component_load_placeholder.dart';
import 'widgets/recipe_toggle_bar.dart';

class MealCookModeScreen extends ConsumerStatefulWidget {
  final String mealId;

  const MealCookModeScreen({super.key, required this.mealId});

  @override
  ConsumerState<MealCookModeScreen> createState() =>
      _MealCookModeScreenState();
}

class _MealCookModeScreenState extends ConsumerState<MealCookModeScreen>
    with WidgetsBindingObserver {
  final _apiClient = getIt<ApiClient>();
  final _timerNotifService = getIt<CookTimerNotificationService>();
  final _liveActivityService = getIt<LiveActivityService>();
  final _recipeCache = getIt<RecipeCacheService>();

  Meal? _meal;
  CookPlan? _plan;
  bool _isLoading = true;
  bool _isOffline = false;
  String? _error;

  // Per-recipe-id retry-in-flight state for the load placeholder.
  final Set<String> _retryingRecipeIds = {};
  // Cache raw API payloads per recipe id so retries don't lossy-round-trip
  // through `_toRawRecipe`. Initially populated by `_loadMealAndRecipes`;
  // a successful `_retryComponent` patches one entry in place.
  final Map<String, Map<String, dynamic>?> _rawRecipes = {};

  // cmmrf-1 — per-recipe step state. Keyed by `recipe_id`. Populated in
  // `_loadMealAndRecipes` once the plan lands (one entry per component,
  // initial value 0). `_activeRecipeId` is the pointer the UI renders;
  // the screen stays in a loading state until both are non-null.
  final Map<String, int> _currentStepByRecipe = {};
  final Map<String, Set<int>> _completedStepsByRecipe = {};
  String? _activeRecipeId;
  // Recipes the user has at any point made active — entered via pill
  // tap, auto-advance, or cross-recipe swipe. Early-finish row
  // inclusion (cmmrf-5) and previousEnteredRecipe (cmmrf-7) both read
  // from this set.
  final Set<String> _enteredRecipeIds = {};

  // cmmrf-3 / cmmrf-6 — recipes whose toggle pill should pulse once
  // (e.g., a timer fired on a non-active recipe). Populated by the
  // timer-completion path; auto-cleared on the pill's AnimatedScale
  // `onEnd` callback.
  final Set<String> _pulsingRecipeIds = {};

  // Stable-key ("componentIndex:orderIndex") set; cmm-4 wires the strip
  // to use these keys directly. cmm-2 only persists checks done while
  // the screen is mounted (no resume restoration yet — cmm-7).
  final Set<String> _checkedIngredientKeys = {};

  late final CookSessionPersister _persister;
  late final CookSessionDebouncer _debouncer;
  String get _sessionKey => CookSessionKey.forMeal(widget.mealId);

  // Timers
  final List<_ActiveTimer> _activeTimers = [];
  Timer? _timerTick;
  Timer? _liveActivityPulse;
  int _nextNotifId = 0;

  final Stopwatch _cookingStopwatch = Stopwatch();
  // cmr-style restored-elapsed bookkeeping; cmm-7 will populate this
  // from the persisted snapshot on Resume.
  int _restoredElapsedMs = 0;
  int? _startedAtMs;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _persister = CookSessionPersister();
    _debouncer = CookSessionDebouncer(_persister);
    _enableWakelock();
    _startTimerTick();
    _initCookSession();
  }

  Future<void> _initCookSession() async {
    final rawPersisted = await _persister.load(_sessionKey);
    if (!mounted) return;
    await _loadMealAndRecipes();
    if (!mounted) return;
    if (_error != null || _plan == null) return;
    if (rawPersisted != null &&
        rawPersisted.targetKind == CookTargetKind.meal) {
      final plan = _plan!;
      // cmmrf-2 — unpack a transitional meal-v1 payload once the plan
      // is available. v2-native payloads pass through unchanged
      // (`unpackLegacyMeal` is a no-op in case a).
      final persisted = rawPersisted.unpackLegacyMeal(plan);
      final stepSummary = _resumeStepSummary(persisted, plan);
      final choice = await showCookResumeGate(
        context,
        state: persisted,
        targetName: _meal?.name ?? widget.mealId,
        totalSteps: plan.totalSteps,
        stepSummaryOverride: stepSummary,
      );
      if (!mounted) return;
      if (choice == CookResumeChoice.resume) {
        _applyRestoredState(persisted, plan);
      } else {
        await _persister.clear(_sessionKey);
        _startedAtMs = DateTime.now().millisecondsSinceEpoch;
      }
    } else {
      _startedAtMs = DateTime.now().millisecondsSinceEpoch;
    }
    if (!mounted) return;
    _cookingStopwatch.start();
  }

  /// Compose the Resume gate's section-aware step phrase.
  /// "Salad · step 2 of 4" on a 3-component plan, clamped if drift.
  /// cmmrf-2 — reads from the v2 per-recipe maps; callers pass the
  /// already-unpacked state (via [CookSessionState.unpackLegacyMeal]).
  String _resumeStepSummary(CookSessionState persisted, CookPlan plan) {
    final activeId = persisted.activeRecipeId ??
        (plan.components.isNotEmpty ? plan.components.first.recipeId : null);
    if (activeId == null) return '';
    final ci = plan.components.indexWhere((c) => c.recipeId == activeId);
    if (ci < 0) return '';
    final component = plan.components[ci];
    if (component.steps.isEmpty) {
      return '${component.name} · step 1 of 1';
    }
    final local = (persisted.currentStepByRecipe[activeId] ?? 0)
        .clamp(0, component.steps.length - 1);
    return '${component.name} · step ${local + 1} of ${component.steps.length}';
  }

  /// cmm-7 / cmmrf-2 — restore in-memory state from a persisted
  /// snapshot. Caller must pass a v2-shape state (via
  /// [CookSessionState.unpackLegacyMeal] if the payload was v1).
  /// Meal-version-drift handling:
  ///   * activeRecipeId no longer in plan → fall back to first
  ///     component + snackbar
  ///   * Per-recipe local step beyond component's step count → clamp
  ///     + snackbar
  ///   * Stable-key references that no longer exist → silently dropped
  ///   * Active timers whose component no longer exists → dropped +
  ///     surfaced in the "while you were away" snackbar
  void _applyRestoredState(CookSessionState state, CookPlan plan) {
    final liveIds = <String>{for (final c in plan.components) c.recipeId};
    var clamped = false;

    String? restoredActiveId = state.activeRecipeId;
    if (restoredActiveId == null || !liveIds.contains(restoredActiveId)) {
      restoredActiveId =
          plan.components.isNotEmpty ? plan.components.first.recipeId : null;
      if (state.activeRecipeId != null &&
          state.activeRecipeId != restoredActiveId) {
        clamped = true;
      }
    }

    final restoredCurrent = <String, int>{};
    final restoredCompleted = <String, Set<int>>{};
    final restoredEntered = <String>{};
    for (final c in plan.components) {
      restoredCurrent[c.recipeId] = 0;
      restoredCompleted[c.recipeId] = <int>{};
    }
    state.currentStepByRecipe.forEach((id, local) {
      if (!liveIds.contains(id)) return;
      final len = plan.stepsFor(id).length;
      if (len == 0) return;
      final clampedLocal = local.clamp(0, len - 1);
      if (clampedLocal != local) clamped = true;
      restoredCurrent[id] = clampedLocal;
      if (clampedLocal > 0) restoredEntered.add(id);
    });
    state.completedStepsByRecipe.forEach((id, localSet) {
      if (!liveIds.contains(id)) return;
      final len = plan.stepsFor(id).length;
      final filtered = <int>{};
      for (final si in localSet) {
        if (si >= 0 && si < len) filtered.add(si);
      }
      restoredCompleted[id] = filtered;
      if (filtered.isNotEmpty) restoredEntered.add(id);
    });
    if (restoredActiveId != null) restoredEntered.add(restoredActiveId);

    // Stable keys live as `<componentIndex>:<orderIndex>` strings.
    // Drop any that don't resolve to a live ingredient.
    final livingKeys = <String>{
      for (final ing in plan.ingredients) ing.stableKey,
    };
    var droppedIngredientKey = false;
    final validChecked = <String>{};
    for (final raw in state.checkedIngredients) {
      if (livingKeys.contains(raw)) {
        validChecked.add(raw);
      } else {
        droppedIngredientKey = true;
      }
    }

    // Rebuild active timers; expired ones surface in the "while away"
    // snackbar with component-name prefixed labels (cmm-5 contract).
    final nowMs = DateTime.now().millisecondsSinceEpoch;
    final restoredTimers = <_ActiveTimer>[];
    final expiredWhileAway = <String>[];
    for (final saved in state.activeTimers) {
      final remainingMs = saved.deadlineMs - nowMs;
      if (remainingMs <= 0) {
        expiredWhileAway.add(saved.label);
        continue;
      }
      final total = Duration(seconds: saved.totalDurationSeconds);
      final startTime =
          DateTime.fromMillisecondsSinceEpoch(saved.deadlineMs).subtract(total);
      final notifId = _nextNotifId++;
      final timer = _ActiveTimer(
        label: saved.label,
        duration: total,
        remaining: Duration(milliseconds: remainingMs),
        startTime: startTime,
        notifId: notifId,
        sourceRecipeId: saved.sourceRecipeId,
      );
      _timerNotifService.scheduleTimerNotification(
        id: notifId,
        label: saved.label,
        expiresAt: DateTime.fromMillisecondsSinceEpoch(saved.deadlineMs),
        recipeId: widget.mealId,
        // Flat step index (for notification telemetry) — computed
        // from the active recipe's local step if available.
        stepIndex: _flatIndexOf(plan, restoredActiveId, restoredCurrent),
        originalDurationSeconds: saved.totalDurationSeconds,
      );
      timer.timer = Timer.periodic(const Duration(seconds: 1), (t) {
        if (!mounted) return;
        final elapsed = DateTime.now().difference(timer.startTime);
        final remaining = timer.duration - elapsed;
        if (remaining.isNegative) {
          t.cancel();
          _onTimerComplete(timer);
        } else {
          setState(() => timer.remaining = remaining);
        }
      });
      restoredTimers.add(timer);
    }

    setState(() {
      _currentStepByRecipe
        ..clear()
        ..addAll(restoredCurrent);
      _completedStepsByRecipe
        ..clear()
        ..addAll(restoredCompleted);
      _activeRecipeId = restoredActiveId;
      _enteredRecipeIds
        ..clear()
        ..addAll(restoredEntered);
      _checkedIngredientKeys
        ..clear()
        ..addAll(validChecked);
      _activeTimers.addAll(restoredTimers);
      _restoredElapsedMs = state.cumulativeElapsedMs;
      _startedAtMs = state.startedAtMs;
    });
    if (restoredTimers.isNotEmpty) _ensureLiveActivityPulse();

    if (clamped && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Meal changed since your last session — picking up at the last step',
          ),
          duration: Duration(seconds: 4),
        ),
      );
    }
    if (droppedIngredientKey && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Ingredients changed since your last session'),
          duration: Duration(seconds: 4),
        ),
      );
    }
    if (expiredWhileAway.isNotEmpty && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(_expiredAwayCopy(expiredWhileAway)),
          duration: const Duration(seconds: 5),
          action: SnackBarAction(label: 'OK', onPressed: () {}),
        ),
      );
    }
  }

  String _expiredAwayCopy(List<String> labels) {
    if (labels.length == 1) {
      return 'While you were away: ${labels.first} timer finished';
    }
    if (labels.length <= 3) {
      final joined = labels.length == 2
          ? '${labels[0]} and ${labels[1]}'
          : '${labels.sublist(0, labels.length - 1).join(', ')}, '
              'and ${labels.last}';
      return 'While you were away: $joined timers finished';
    }
    return 'While you were away: ${labels.length} timers finished';
  }

  Future<void> _loadMealAndRecipes() async {
    try {
      final meal = await ref.read(mealByIdProvider(widget.mealId).future);
      if (!mounted) return;
      final ordered = [...meal.components]
        ..sort((a, b) => a.orderIndex.compareTo(b.orderIndex));
      // Parallel fetch — cmm-2 AC10 perf bound is < 400ms in mocks.
      final fetched = await Future.wait(
        ordered.map(_fetchRecipeWithOfflineFallback),
        eagerError: false,
      );
      if (!mounted) return;
      _rawRecipes
        ..clear()
        ..addEntries([
          for (var i = 0; i < ordered.length; i++)
            MapEntry(ordered[i].recipeId, fetched[i]),
        ]);
      final orderedMeal = meal.copyWith(components: ordered);
      final plan = CookPlan.fromMeal(orderedMeal, fetched);
      setState(() {
        _meal = orderedMeal;
        _plan = plan;
        _seedPerRecipeMaps(plan);
        _isLoading = false;
      });
    } on DioException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Could not load this meal: ${e.message ?? e.type.name}';
        _isLoading = false;
      });
    } catch (e, st) {
      ErrorReporter.report(e, st,
          area: 'cook.meal', operation: 'loadMealAndRecipes');
      if (!mounted) return;
      setState(() {
        _error = "Could not load this meal";
        _isLoading = false;
      });
    }
  }

  /// Fetch a recipe; on a network-class DioException fall back to the
  /// local recipe cache. cmm-2 AC3 / AC8 / AC9 — offline degrade per
  /// component. Returns `null` only when both the live fetch AND the
  /// cache are empty for this recipe.
  Future<Map<String, dynamic>?> _fetchRecipeWithOfflineFallback(
      MealComponent component) async {
    try {
      final response = await _apiClient.getRecipe(component.recipeId);
      final data = response.data as Map<String, dynamic>;
      // Cache on success so future offline cooks work.
      await _recipeCache.cacheRecipe(component.recipeId, data);
      return data;
    } on DioException catch (e) {
      if (_isNetworkError(e)) {
        final cached =
            await _recipeCache.loadCachedRecipe(component.recipeId);
        if (cached != null) {
          if (mounted && !_isOffline) {
            setState(() => _isOffline = true);
          }
          return cached;
        }
      }
      ErrorReporter.report(e, StackTrace.current,
          area: 'cook.meal',
          operation: 'fetchComponentRecipe',
          extras: {
            'meal_id': widget.mealId,
            'recipe_id': component.recipeId,
          });
      return null;
    } catch (e, st) {
      ErrorReporter.report(e, st,
          area: 'cook.meal',
          operation: 'fetchComponentRecipe',
          extras: {
            'meal_id': widget.mealId,
            'recipe_id': component.recipeId,
          });
      return null;
    }
  }

  bool _isNetworkError(DioException e) {
    return e.type == DioExceptionType.connectionError ||
        e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.sendTimeout ||
        e.type == DioExceptionType.receiveTimeout;
  }

  Future<void> _retryComponent(String recipeId) async {
    final plan = _plan;
    final meal = _meal;
    if (plan == null || meal == null) return;
    if (_retryingRecipeIds.contains(recipeId)) return;
    final componentIndex =
        plan.components.indexWhere((c) => c.recipeId == recipeId);
    if (componentIndex < 0) return;
    setState(() => _retryingRecipeIds.add(recipeId));
    final component = meal.components[componentIndex];
    final fresh = await _fetchRecipeWithOfflineFallback(component);
    if (!mounted) return;
    if (fresh != null) {
      _rawRecipes[recipeId] = fresh;
      // Rebuild plan from the cached raw payloads — lossless and
      // ignores in-flight peer retries (each retry only mutates its
      // own entry in `_rawRecipes`).
      final raws = <Map<String, dynamic>?>[
        for (final c in meal.components) _rawRecipes[c.recipeId],
      ];
      final next = CookPlan.fromMeal(meal, raws);
      // cmmrf-1 — per-recipe maps are naturally stable across plan
      // rebuilds (keyed by recipeId). Clamp each recipe's current +
      // completed step indices to the new component length; drop
      // entries for components that no longer exist (shouldn't happen
      // in cmm-2 but defends cmm-7's drift logic).
      _clampPerRecipeMapsToPlan(next);
      setState(() {
        _plan = next;
        _seedPerRecipeMaps(next);
        _retryingRecipeIds.remove(recipeId);
      });
      _persistState();
    } else {
      setState(() => _retryingRecipeIds.remove(recipeId));
    }
  }

  /// Drop entries for missing recipes + clamp each recipe's current +
  /// completed step indices to the new component length. Called after
  /// a plan rebuild (e.g., successful component retry) to keep the
  /// per-recipe maps in sync with the live plan shape.
  void _clampPerRecipeMapsToPlan(CookPlan newPlan) {
    final liveByLen = <String, int>{
      for (final c in newPlan.components) c.recipeId: c.steps.length,
    };
    _currentStepByRecipe.removeWhere((id, _) => !liveByLen.containsKey(id));
    _completedStepsByRecipe.removeWhere((id, _) => !liveByLen.containsKey(id));
    _enteredRecipeIds.removeWhere((id) => !liveByLen.containsKey(id));
    for (final entry in liveByLen.entries) {
      final len = entry.value;
      if (len == 0) continue;
      final cur = _currentStepByRecipe[entry.key];
      if (cur != null && cur >= len) {
        _currentStepByRecipe[entry.key] = len - 1;
      }
      final completed = _completedStepsByRecipe[entry.key];
      if (completed != null) {
        completed.removeWhere((si) => si < 0 || si >= len);
      }
    }
    final active = _activeRecipeId;
    if (active != null && !liveByLen.containsKey(active)) {
      _activeRecipeId = newPlan.components.isNotEmpty
          ? newPlan.components.first.recipeId
          : null;
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    unawaited(_debouncer.flushNow());
    _disableWakelock();
    _timerTick?.cancel();
    _liveActivityPulse?.cancel();
    _cookingStopwatch.stop();
    for (final timer in _activeTimers) {
      timer.timer?.cancel();
      _timerNotifService.cancelTimerNotification(timer.notifId);
      _liveActivityService.endTimerActivity(timer.notifId);
    }
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // cmm-2 AC11 — paused-flush mirrors cmr-2's pattern so the meal
    // session survives an OS kill mid-cook.
    if (state == AppLifecycleState.paused) {
      unawaited(_debouncer.flushNow());
    }
    if (state == AppLifecycleState.resumed && mounted) {
      // Reconcile timer countdowns the same way recipe cook does.
      final now = DateTime.now();
      final expired = <_ActiveTimer>[];
      setState(() {
        for (final t in _activeTimers) {
          final elapsed = now.difference(t.startTime);
          final remaining = t.duration - elapsed;
          if (remaining.isNegative || remaining == Duration.zero) {
            expired.add(t);
          } else {
            t.remaining = remaining;
          }
        }
      });
      for (final t in expired) {
        t.timer?.cancel();
        _onTimerComplete(t);
      }
    }
  }

  void _enableWakelock() async {
    await WakelockPlus.enable();
  }

  void _disableWakelock() async {
    await WakelockPlus.disable();
  }

  void _startTimerTick() {
    _timerTick = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) return;
      if (_activeTimers.isNotEmpty || _cookingStopwatch.isRunning) {
        setState(() {});
      }
    });
  }

  // -----------------------------------------------------------------
  // Step navigation (cmmrf-1 / cmmrf-4 — per-recipe maps; a flat index
  // is synthesized only for notification telemetry via _flatCurrentStep.)
  // -----------------------------------------------------------------

  /// Seed [_currentStepByRecipe] / [_completedStepsByRecipe] with an
  /// entry per component (all starting at 0 / empty), and pin
  /// [_activeRecipeId] to plan order position 0. Idempotent — safe to
  /// call again on plan rebuild; existing entries are preserved, new
  /// components get seeded, and [_activeRecipeId] is only (re)assigned
  /// when null or stale.
  void _seedPerRecipeMaps(CookPlan plan) {
    for (final c in plan.components) {
      _currentStepByRecipe.putIfAbsent(c.recipeId, () => 0);
      _completedStepsByRecipe.putIfAbsent(c.recipeId, () => <int>{});
    }
    // Drop entries for components no longer in the plan.
    final liveIds = {for (final c in plan.components) c.recipeId};
    _currentStepByRecipe.removeWhere((id, _) => !liveIds.contains(id));
    _completedStepsByRecipe.removeWhere((id, _) => !liveIds.contains(id));
    _enteredRecipeIds.removeWhere((id) => !liveIds.contains(id));
    final active = _activeRecipeId;
    if (active == null || !liveIds.contains(active)) {
      _activeRecipeId =
          plan.components.isNotEmpty ? plan.components.first.recipeId : null;
    }
    final pinned = _activeRecipeId;
    if (pinned != null) _enteredRecipeIds.add(pinned);
  }

  int get _flatCurrentStep {
    final plan = _plan;
    final activeId = _activeRecipeId;
    if (plan == null || activeId == null) return 0;
    final ci = plan.components.indexWhere((c) => c.recipeId == activeId);
    if (ci < 0) return 0;
    final local = _currentStepByRecipe[activeId] ?? 0;
    final clamped = local.clamp(0, plan.components[ci].steps.length - 1);
    return plan.flatIndexFor(ci, clamped);
  }

  /// cmmrf-4 — tap handler for a StepNavigator pill. The navigator
  /// now renders the active recipe's local pills only (cross-recipe
  /// pill rows are gone), so `localStep` is local to the active
  /// recipe. Rewinds the active recipe's completed set when moving
  /// backward within the recipe.
  void _goToStep(int localStep) {
    final plan = _plan;
    final activeId = _activeRecipeId;
    if (plan == null || activeId == null) return;
    final ci = plan.components.indexWhere((c) => c.recipeId == activeId);
    if (ci < 0) return;
    final len = plan.components[ci].steps.length;
    if (localStep < 0 || localStep >= len) return;
    HapticFeedback.selectionClick();
    setState(() {
      final cur = _currentStepByRecipe[activeId] ?? 0;
      if (localStep < cur) {
        _completedStepsByRecipe[activeId]?.remove(localStep);
      }
      _currentStepByRecipe[activeId] = localStep;
      _completedStepsByRecipe.putIfAbsent(activeId, () => <int>{});
    });
    _persistState();
  }

  void _nextStep() {
    final plan = _plan;
    final activeId = _activeRecipeId;
    if (plan == null || activeId == null) return;
    final activeCi =
        plan.components.indexWhere((c) => c.recipeId == activeId);
    if (activeCi < 0) return;
    final steps = plan.components[activeCi].steps;
    if (steps.isEmpty) return;
    final cur = _currentStepByRecipe[activeId] ?? 0;
    _completedStepsByRecipe.putIfAbsent(activeId, () => <int>{}).add(cur);
    if (cur < steps.length - 1) {
      HapticFeedback.selectionClick();
      setState(() {
        _currentStepByRecipe[activeId] = cur + 1;
      });
      _persistState();
    } else {
      _autoAdvanceRecipe();
    }
  }

  void _previousStep() {
    final plan = _plan;
    final activeId = _activeRecipeId;
    if (plan == null || activeId == null) return;
    final cur = _currentStepByRecipe[activeId] ?? 0;
    if (cur > 0) {
      HapticFeedback.selectionClick();
      setState(() {
        _currentStepByRecipe[activeId] = cur - 1;
        _completedStepsByRecipe[activeId]?.remove(cur - 1);
      });
      _persistState();
      return;
    }
    // Local step 0 — cross-recipe rewind to the prior entered recipe
    // at its last-visited step (cmmrf-7 wires the swipe path through
    // this same method).
    final prior = plan.previousEnteredRecipe(activeId, _enteredRecipeIds);
    if (prior == null) return;
    final priorSteps = plan.stepsFor(prior);
    if (priorSteps.isEmpty) return;
    final priorLastVisited = (_currentStepByRecipe[prior] ?? 0)
        .clamp(0, priorSteps.length - 1);
    HapticFeedback.selectionClick();
    setState(() {
      _activeRecipeId = prior;
      _currentStepByRecipe[prior] = priorLastVisited;
    });
    _persistState();
  }

  /// Toggle-bar pill tap handler (cmmrf-3 mount site; cmmrf-1 logic).
  /// Same-recipe taps are swallowed silently; load-failed components
  /// are no-ops. Otherwise switches [_activeRecipeId], marks the
  /// recipe as entered, and persists.
  void _setActiveRecipe(String recipeId) {
    final plan = _plan;
    if (plan == null) return;
    if (recipeId == _activeRecipeId) return;
    final ci = plan.components.indexWhere((c) => c.recipeId == recipeId);
    if (ci < 0) return;
    if (plan.components[ci].loadFailed) return;
    HapticFeedback.selectionClick();
    setState(() {
      _activeRecipeId = recipeId;
      _enteredRecipeIds.add(recipeId);
      _currentStepByRecipe.putIfAbsent(recipeId, () => 0);
      _completedStepsByRecipe.putIfAbsent(recipeId, () => <int>{});
    });
    _persistState();
  }

  /// cmmrf-1 / cmmrf-5 — advances to the next unfinished recipe in
  /// plan order (wrapping), lands on its first step, and marks it
  /// entered. When no unfinished recipe remains, hands off to the
  /// unified post-cook entry point — same path as "Finish cooking
  /// now" and the Done button.
  void _autoAdvanceRecipe() {
    final plan = _plan;
    final activeId = _activeRecipeId;
    if (plan == null || activeId == null) return;
    final next = plan.nextUnfinishedRecipeAfter(
      activeId,
      _currentStepByRecipe,
      _completedStepsByRecipe,
    );
    if (next == null) {
      unawaited(_openPostCookForEnteredRecipes());
      return;
    }
    HapticFeedback.selectionClick();
    setState(() {
      _activeRecipeId = next;
      _enteredRecipeIds.add(next);
      _currentStepByRecipe[next] = 0;
      _completedStepsByRecipe.putIfAbsent(next, () => <int>{});
    });
    _persistState();
  }

  void _markAllUpToHere() {
    final plan = _plan;
    final activeId = _activeRecipeId;
    if (plan == null || activeId == null) return;
    final activeCi =
        plan.components.indexWhere((c) => c.recipeId == activeId);
    if (activeCi < 0) return;
    // Same intent as the legacy flat-index version: mark every step up
    // to and including the current flat position as complete. Per
    // recipe that means: all steps of every prior component, plus the
    // active component's steps up to its current local index.
    HapticFeedback.mediumImpact();
    setState(() {
      for (var ci = 0; ci <= activeCi; ci++) {
        final comp = plan.components[ci];
        final target =
            _completedStepsByRecipe.putIfAbsent(comp.recipeId, () => <int>{});
        final upTo = ci < activeCi
            ? comp.steps.length - 1
            : (_currentStepByRecipe[activeId] ?? 0);
        for (var si = 0; si <= upTo; si++) {
          target.add(si);
        }
      }
    });
    _persistState();
  }

  void _toggleIngredient(int flatIndex) {
    final plan = _plan;
    if (plan == null || flatIndex < 0 || flatIndex >= plan.ingredients.length) {
      return;
    }
    final key = plan.ingredients[flatIndex].stableKey;
    HapticFeedback.selectionClick();
    setState(() {
      if (_checkedIngredientKeys.contains(key)) {
        _checkedIngredientKeys.remove(key);
      } else {
        _checkedIngredientKeys.add(key);
      }
    });
    _persistState();
  }

  Set<int> get _checkedFlatIndices {
    final plan = _plan;
    if (plan == null) return const {};
    final out = <int>{};
    for (var i = 0; i < plan.ingredients.length; i++) {
      if (_checkedIngredientKeys.contains(plan.ingredients[i].stableKey)) {
        out.add(i);
      }
    }
    return out;
  }

  // -----------------------------------------------------------------
  // Timers (cmm-5 will layer in component-aware label disambiguation)
  // -----------------------------------------------------------------

  void _startTimer(Duration duration, String label) {
    HapticFeedback.mediumImpact();
    final notifId = _nextNotifId++;
    final startTime = DateTime.now();
    final expiresAt = startTime.add(duration);
    final mealName = _meal?.name ?? 'Meal';
    final plan = _plan;
    final activeId = _activeRecipeId;
    final componentName = (plan != null && activeId != null)
        ? _componentNameFor(plan, activeId)
        : null;
    // cmm-5 — component-name disambiguation. If another active timer
    // already uses this exact label (typically from a different
    // component), prefix the NEW timer's display label with the
    // current component name + " · ". First-come-first-served: the
    // existing timer's label is NOT retroactively renamed.
    final displayLabel = _disambiguateMealTimerLabel(
      requested: label,
      currentComponentName: componentName,
    );
    final activeTimer = _ActiveTimer(
      label: displayLabel,
      duration: duration,
      remaining: duration,
      startTime: startTime,
      notifId: notifId,
      sourceRecipeId: activeId,
    );
    _timerNotifService.scheduleTimerNotification(
      id: notifId,
      label: displayLabel,
      expiresAt: expiresAt,
      recipeId: widget.mealId,
      stepIndex: _flatCurrentStep,
      originalDurationSeconds: duration.inSeconds,
    );
    _liveActivityService.startTimerActivity(
      notifId: notifId,
      timerLabel: displayLabel,
      recipeName: mealName,
      duration: duration,
    );
    _ensureLiveActivityPulse();
    activeTimer.timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (mounted) {
        final elapsed = DateTime.now().difference(activeTimer.startTime);
        final remaining = duration - elapsed;
        if (remaining.isNegative) {
          timer.cancel();
          _onTimerComplete(activeTimer);
        } else {
          setState(() {
            activeTimer.remaining = remaining;
          });
        }
      }
    });
    setState(() => _activeTimers.add(activeTimer));
    _persistState();
  }

  void _cancelTimer(_ActiveTimer timer) {
    timer.timer?.cancel();
    _timerNotifService.cancelTimerNotification(timer.notifId);
    _liveActivityService.endTimerActivity(timer.notifId);
    setState(() => _activeTimers.remove(timer));
    _maybeStopLiveActivityPulse();
    _persistState();
  }

  void _restartTimer(_ActiveTimer timer) {
    timer.timer?.cancel();
    _timerNotifService.cancelTimerNotification(timer.notifId);
    _liveActivityService.endTimerActivity(timer.notifId);
    setState(() => _activeTimers.remove(timer));
    _startTimer(timer.duration, timer.label);
  }

  void _onTimerComplete(_ActiveTimer timer) {
    if (!mounted) return;
    HapticFeedback.heavyImpact();
    _timerNotifService.cancelTimerNotification(timer.notifId);
    _liveActivityService.completeTimerActivity(timer.notifId);
    setState(() => _activeTimers.remove(timer));
    _maybeStopLiveActivityPulse();
    _persistState();
    showTimerCompletionOverlay(
      context: context,
      label: timer.label,
      recipeName: _meal?.name,
      stepNumber: _flatCurrentStep,
      onAdd2: () =>
          _startTimer(const Duration(minutes: 2), '${timer.label} (+2m)'),
      onAdd5: () =>
          _startTimer(const Duration(minutes: 5), '${timer.label} (+5m)'),
      onReset: () => _startTimer(timer.duration, timer.label),
      onStop: () {},
    );
  }

  void _ensureLiveActivityPulse() {
    if (_liveActivityPulse != null) return;
    _liveActivityPulse = Timer.periodic(const Duration(minutes: 1), (_) {
      if (!mounted || _activeTimers.isEmpty) return;
      final now = DateTime.now();
      for (final t in _activeTimers) {
        final elapsed = now.difference(t.startTime);
        final remaining = t.duration - elapsed;
        if (remaining.isNegative) continue;
        _liveActivityService.updateTimerActivity(
          notifId: t.notifId,
          newRemaining: remaining,
        );
      }
    });
  }

  void _maybeStopLiveActivityPulse() {
    if (_activeTimers.isNotEmpty) return;
    _liveActivityPulse?.cancel();
    _liveActivityPulse = null;
  }

  Future<void> _showManualTimerSheet() async {
    final result = await showModalBottomSheet<(int, String)>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Theme.of(context).colorScheme.surface,
      builder: (_) => const ManualTimerSheet(),
    );
    if (result == null || !mounted) return;
    final (minutes, rawLabel) = result;
    // cmm-5 AC3 — manual-timer label semantics in meal cook:
    //  * Empty / sheet-default ("Timer") → fall back to the current
    //    component name (e.g. "Dressing"). Same-component repeats
    //    pick up the legacy " 2" / " 3" suffix via the shared
    //    `disambiguateTimerLabel`.
    //  * Non-empty user labels go straight to `_startTimer`, which
    //    applies the cmm-5 component-prefix rule on collisions.
    final plan = _plan;
    final activeId = _activeRecipeId;
    final componentName = (plan != null && activeId != null)
        ? _componentNameFor(plan, activeId)
        : null;
    final trimmed = rawLabel.trim();
    final isDefaultLabel =
        trimmed.isEmpty || trimmed == kManualTimerDefaultLabel;
    if (isDefaultLabel &&
        componentName != null &&
        componentName.isNotEmpty) {
      final uniqueLabel = disambiguateTimerLabel(
        componentName,
        _activeTimers.map((t) => t.label),
      );
      _startTimer(Duration(minutes: minutes), uniqueLabel);
      return;
    }
    final label = trimmed.isEmpty ? kManualTimerDefaultLabel : trimmed;
    _startTimer(Duration(minutes: minutes), label);
  }

  /// cmm-5 AC2 — when starting a new timer whose label collides with
  /// an existing active timer's label, prefix the NEW timer with the
  /// current component name + " · ". First-come-first-served: the
  /// existing timer's label is preserved verbatim. Returns the
  /// requested label unchanged when no collision exists or when the
  /// component name isn't known (recipe cook path also returns
  /// requested unchanged because the prefix would be redundant).
  String _disambiguateMealTimerLabel({
    required String requested,
    required String? currentComponentName,
  }) {
    if (currentComponentName == null || currentComponentName.isEmpty) {
      return requested;
    }
    final existingLabels = _activeTimers.map((t) => t.label).toSet();
    if (!existingLabels.contains(requested)) return requested;
    var prefixed = '$currentComponentName · $requested';
    var n = 2;
    while (existingLabels.contains(prefixed)) {
      prefixed = '$currentComponentName · $requested $n';
      n++;
    }
    return prefixed;
  }

  // -----------------------------------------------------------------
  // Persistence
  //
  // cmmrf-1 keeps the v1 wire format via the flatten-on-save shim
  // below; cmmrf-2 swaps this for native v2 serialization.
  // -----------------------------------------------------------------

  void _persistState() {
    _debouncer.markDirty(_sessionKey, _buildSnapshot);
  }

  CookSessionState _buildSnapshot() {
    final nowMs = DateTime.now().millisecondsSinceEpoch;
    _startedAtMs ??= nowMs;
    final checked = _checkedIngredientKeys.toList()..sort();
    final currentMap = Map<String, int>.from(_currentStepByRecipe);
    final completedMap = <String, Set<int>>{
      for (final entry in _completedStepsByRecipe.entries)
        entry.key: Set<int>.from(entry.value),
    };
    return CookSessionState(
      targetKind: CookTargetKind.meal,
      targetId: widget.mealId,
      startedAtMs: _startedAtMs!,
      cumulativeElapsedMs:
          _restoredElapsedMs + _cookingStopwatch.elapsedMilliseconds,
      activeRecipeId: _activeRecipeId,
      currentStepByRecipe: currentMap,
      completedStepsByRecipe: completedMap,
      checkedIngredients: checked,
      activeTimers: _activeTimers
          .map(
            (t) => SavedTimerState(
              label: t.label,
              deadlineMs: t.startTime.add(t.duration).millisecondsSinceEpoch,
              totalDurationSeconds: t.duration.inSeconds,
              source: 'manual',
              sourceRecipeId: t.sourceRecipeId,
            ),
          )
          .toList(),
      updatedAtMs: nowMs,
    );
  }

  /// Lookup helper for a component's display name by recipe id. Used
  /// by timer-start / manual-timer / post-cook paths that read the
  /// "current component" context.
  String? _componentNameFor(CookPlan plan, String recipeId) {
    for (final c in plan.components) {
      if (c.recipeId == recipeId) return c.name;
    }
    return null;
  }

  /// True when the active recipe has a local next step, or any other
  /// component has unfinished work reachable via auto-advance.
  /// Drives `StepNavigator.onNext` enablement (cmmrf-4) — when false,
  /// the button flips to "Done".
  bool _canGoNext(CookPlan plan, String activeId) {
    final ci = plan.components.indexWhere((c) => c.recipeId == activeId);
    if (ci < 0) return false;
    final len = plan.components[ci].steps.length;
    final cur = _currentStepByRecipe[activeId] ?? 0;
    if (len > 0 && cur < len - 1) return true;
    return plan.nextUnfinishedRecipeAfter(
          activeId,
          _currentStepByRecipe,
          _completedStepsByRecipe,
        ) !=
        null;
  }

  /// True when Prev within the active recipe is legal, or there is a
  /// prior entered recipe to rewind to (cmmrf-7 wires the swipe path
  /// through the same `_previousStep`).
  bool _canGoPrev(CookPlan plan, String activeId) {
    final cur = _currentStepByRecipe[activeId] ?? 0;
    if (cur > 0) return true;
    return plan.previousEnteredRecipe(activeId, _enteredRecipeIds) != null;
  }

  /// Flat index (for notification telemetry) derived from the active
  /// recipe's local step. Defensive — returns 0 if the active recipe
  /// is missing from the plan.
  int _flatIndexOf(
    CookPlan plan,
    String? activeId,
    Map<String, int> currentByRecipe,
  ) {
    if (activeId == null) return 0;
    final ci = plan.components.indexWhere((c) => c.recipeId == activeId);
    if (ci < 0) return 0;
    final len = plan.components[ci].steps.length;
    if (len == 0) return 0;
    final local = (currentByRecipe[activeId] ?? 0).clamp(0, len - 1);
    return plan.flatIndexFor(ci, local);
  }

  // -----------------------------------------------------------------
  // Reset / exit
  // -----------------------------------------------------------------

  Future<void> _confirmAndResetCook() async {
    final confirmed = await showCookResetConfirmSheet(context);
    if (!confirmed || !mounted) return;
    for (final timer in List<_ActiveTimer>.from(_activeTimers)) {
      timer.timer?.cancel();
      _timerNotifService.cancelTimerNotification(timer.notifId);
      _liveActivityService.endTimerActivity(timer.notifId);
    }
    _maybeStopLiveActivityPulse();
    _debouncer.discardPending();
    await _persister.clear(_sessionKey);
    if (!mounted) return;
    setState(() {
      final plan = _plan;
      _currentStepByRecipe
        ..clear()
        ..addEntries([
          if (plan != null)
            for (final c in plan.components) MapEntry(c.recipeId, 0),
        ]);
      _completedStepsByRecipe
        ..clear()
        ..addEntries([
          if (plan != null)
            for (final c in plan.components) MapEntry(c.recipeId, <int>{}),
        ]);
      _enteredRecipeIds.clear();
      if (plan != null && plan.components.isNotEmpty) {
        _activeRecipeId = plan.components.first.recipeId;
        _enteredRecipeIds.add(plan.components.first.recipeId);
      }
      _checkedIngredientKeys.clear();
      _activeTimers.clear();
      _cookingStopwatch.stop();
      _cookingStopwatch.reset();
      _cookingStopwatch.start();
      _restoredElapsedMs = 0;
      _startedAtMs = DateTime.now().millisecondsSinceEpoch;
    });
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Cook session reset'),
        duration: Duration(seconds: 2),
      ),
    );
  }

  void _exitCookMode() {
    _cookingStopwatch.stop();
    final activeId = _activeRecipeId;
    if (_plan != null && activeId != null) {
      final cur = _currentStepByRecipe[activeId] ?? 0;
      _completedStepsByRecipe.putIfAbsent(activeId, () => <int>{}).add(cur);
    }
    context.pop();
  }

  /// cmmrf-5 — Done button handler. Marks the active recipe's current
  /// step complete (so the immediate step is reflected in the seed
  /// set), then hands off to the unified post-cook entry point.
  Future<void> _finishCooking() async {
    final plan = _plan;
    if (plan == null) return;
    final activeId = _activeRecipeId;
    if (activeId != null) {
      final cur = _currentStepByRecipe[activeId] ?? 0;
      _completedStepsByRecipe.putIfAbsent(activeId, () => <int>{}).add(cur);
    }
    await _openPostCookForEnteredRecipes();
  }

  /// cmmrf-5 — single post-cook entry point. Used by the Done button,
  /// the overflow "Finish cooking now" flow, and the auto-advance
  /// null-return case. Row seed filters by `_enteredRecipeIds` (any
  /// component the user has made active) and excludes load-failed
  /// components so placeholders don't leak into the rating sheet.
  Future<void> _openPostCookForEnteredRecipes() async {
    final plan = _plan;
    if (plan == null) return;
    HapticFeedback.heavyImpact();
    _cookingStopwatch.stop();
    final ratables = <ComponentRatable>[];
    for (final c in plan.components) {
      if (c.loadFailed) continue;
      if (_enteredRecipeIds.contains(c.recipeId)) {
        ratables.add(
            ComponentRatable(recipeId: c.recipeId, displayName: c.name));
      }
    }
    if (ratables.isEmpty) {
      _debouncer.discardPending();
      await _persister.clear(_sessionKey);
      if (mounted) context.pop();
      return;
    }
    await _openPostCookSheet(ratables);
  }

  /// cmm-6 — overflow "Finish cooking now" item. Confirmation sheet
  /// then opens post-cook seeded with components in
  /// `_enteredRecipeIds` (any component the user has made active, via
  /// pill tap / auto-advance / cross-recipe rewind).
  Future<void> _finishCookingEarly() async {
    final plan = _plan;
    if (plan == null) return;
    final confirmed = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: context.cookModeTheme.cookSurface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (sheetContext) {
        final cook = sheetContext.cookModeTheme;
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(24, 20, 24, 24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'Finish this meal early?',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: cook.cookOnSurface,
                  ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  "You'll be asked to rate the components you've cooked so far.",
                  style: TextStyle(
                    fontSize: 14,
                    color: cook.cookOnSurface.withValues(alpha: 0.7),
                  ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 20),
                Row(
                  children: [
                    Expanded(
                      child: TextButton(
                        key: const Key('finish_early_cancel'),
                        onPressed: () => Navigator.of(sheetContext).pop(false),
                        child: const Text('Cancel'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: FilledButton(
                        key: const Key('finish_early_confirm'),
                        onPressed: () => Navigator.of(sheetContext).pop(true),
                        style: FilledButton.styleFrom(
                          backgroundColor:
                              Theme.of(sheetContext).colorScheme.error,
                          foregroundColor:
                              Theme.of(sheetContext).colorScheme.onError,
                        ),
                        child: const Text('Finish'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
    if (!mounted || confirmed != true) return;
    // cmmrf-5 — delegate to the unified entry point.
    await _openPostCookForEnteredRecipes();
  }

  Future<void> _openPostCookSheet(List<ComponentRatable> ratables) async {
    await showModalBottomSheet<void>(
      context: context,
      isDismissible: false,
      enableDrag: false,
      isScrollControlled: true,
      backgroundColor: context.cookModeTheme.cookSurface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (sheetContext) => PostCookFeedbackSheet(
        components: ratables,
        title: _meal?.name,
        apiClient: _apiClient,
        recipeCache: _recipeCache,
        isOffline: _isOffline,
        onComplete: ({bool saved = false}) {
          if (saved) {
            _debouncer.discardPending();
            unawaited(_persister.clear(_sessionKey));
          }
          if (sheetContext.mounted) Navigator.of(sheetContext).pop();
        },
      ),
    );
    if (mounted) context.pop();
  }

  String _formatDuration(Duration d) {
    final minutes = d.inMinutes;
    final seconds = d.inSeconds % 60;
    return '${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
  }

  // -----------------------------------------------------------------
  // Build
  // -----------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    final cook = context.cookModeTheme;
    if (_isLoading) {
      return Scaffold(
        backgroundColor: cook.cookSurface,
        body: Center(
          child: CircularProgressIndicator(color: cook.cookAccent),
        ),
      );
    }
    final error = _error;
    if (error != null) {
      return Scaffold(
        backgroundColor: cook.cookSurface,
        appBar: AppBar(
          backgroundColor: cook.cookSurface,
          iconTheme: IconThemeData(color: cook.cookOnSurface),
        ),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: cook.cookError.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    error,
                    style: TextStyle(color: cook.cookOnSurface),
                    textAlign: TextAlign.center,
                  ),
                ),
                const SizedBox(height: 16),
                ElevatedButton(
                  key: const Key('meal_cook_retry'),
                  onPressed: _retryFullLoad,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: cook.cookError,
                    foregroundColor: cook.cookOnAccent,
                  ),
                  child: const Text('Retry'),
                ),
              ],
            ),
          ),
        ),
      );
    }
    final plan = _plan!;
    // Guard: `_loadMealAndRecipes` always seeds `_activeRecipeId` and
    // per-recipe maps when the plan lands, so these should never be
    // null at this point. Fall back to the first component defensively
    // in case of an unexpected race.
    final activeId =
        _activeRecipeId ?? plan.components.first.recipeId;
    final activeCi =
        plan.components.indexWhere((c) => c.recipeId == activeId);
    final safeCi = activeCi < 0 ? 0 : activeCi;
    final currentComponent = plan.components[safeCi];
    final maxLocal = currentComponent.steps.isEmpty
        ? 0
        : currentComponent.steps.length - 1;
    final activeLocalStep =
        (_currentStepByRecipe[activeId] ?? 0).clamp(0, maxLocal);
    final canGoNext = _canGoNext(plan, activeId);
    final canGoPrev = _canGoPrev(plan, activeId);
    return Scaffold(
      backgroundColor: cook.cookSurface,
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(context, cook, plan),
            if (plan.hasAnyLoadFailures) _buildPartialLoadBanner(context, cook, plan),
            if (_activeTimers.isNotEmpty)
              ActiveTimersRow<_ActiveTimer>(
                timers: _activeTimers,
                onTap: _showTimerDetailSheet,
                onCancel: _cancelTimer,
              ),
            IngredientStrip(
              ingredients:
                  plan.ingredients.map((i) => i.raw).toList(growable: false),
              checkedIndices: _checkedFlatIndices,
              onToggle: _toggleIngredient,
              // cmm-4 — every chip carries a tag chip (compact view) /
              // group divider (expanded view) bearing its source
              // component name. 1-component plans skip the builder
              // entirely (recipe cook keeps `null`).
              sourceTagBuilder: plan.components.length > 1
                  ? (i) {
                      if (i < 0 || i >= plan.ingredients.length) return null;
                      return plan.ingredients[i].sourceComponentName;
                    }
                  : null,
            ),
            // cmmrf-3 — toggle bar between ingredients and step card.
            // Hidden for single-component meals (renders SizedBox.shrink).
            RecipeToggleBar(
              components: [
                for (final c in plan.components)
                  plan.summaryFor(
                    c.recipeId,
                    _currentStepByRecipe,
                    _completedStepsByRecipe,
                  ),
              ],
              activeRecipeId: activeId,
              pulsingRecipeIds: _pulsingRecipeIds,
              onTap: _setActiveRecipe,
              onPulseEnd: (id) {
                if (!mounted) return;
                setState(() => _pulsingRecipeIds.remove(id));
              },
            ),
            Divider(height: 1, color: cook.cookDivider),
            Expanded(
              child: GestureDetector(
                onHorizontalDragEnd: (details) {
                  if (details.primaryVelocity != null) {
                    if (details.primaryVelocity! < -500) {
                      _nextStep();
                    } else if (details.primaryVelocity! > 500) {
                      _previousStep();
                    }
                  }
                },
                onTapUp: (details) {
                  final screenWidth = MediaQuery.of(context).size.width;
                  final tapX = details.localPosition.dx;
                  if (tapX < screenWidth * 0.25) {
                    if (canGoPrev) _previousStep();
                  } else if (tapX > screenWidth * 0.75) {
                    if (canGoNext) _nextStep();
                  }
                },
                child: _buildStepContent(
                  context,
                  cook,
                  plan,
                  safeCi,
                  activeLocalStep,
                  currentComponent,
                ),
              ),
            ),
            StepNavigator(
              // cmmrf-4 — navigator renders the active recipe's local
              // pills. Cross-recipe context lives in the toggle bar.
              currentStep: activeLocalStep,
              totalSteps: currentComponent.steps.length,
              completedSteps:
                  _completedStepsByRecipe[activeId] ?? const <int>{},
              onPrevious: canGoPrev ? _previousStep : null,
              onNext: canGoNext ? _nextStep : null,
              onDone: _finishCooking,
              onStepTap: _goToStep,
              onLongPressStep: _markAllUpToHere,
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _retryFullLoad() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    await _loadMealAndRecipes();
  }

  Widget _buildHeader(BuildContext context, CookModeTheme cook, CookPlan plan) {
    return Container(
      padding: const EdgeInsets.fromLTRB(8, 4, 12, 4),
      color: cook.cookSurface,
      child: Row(
        children: [
          IconButton(
            icon: Icon(Icons.arrow_back, color: cook.cookOnSurface),
            onPressed: _exitCookMode,
            constraints: const BoxConstraints(minWidth: 64, minHeight: 64),
            padding: EdgeInsets.zero,
          ),
          Expanded(
            child: Text(
              plan.title,
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: cook.cookOnSurface,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          IconButton(
            icon: Icon(Icons.timer_outlined, color: cook.cookOnSurface),
            onPressed: _showManualTimerSheet,
            constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
            padding: EdgeInsets.zero,
            tooltip: 'Add a timer',
          ),
          if (_isOffline) ...[
            const SizedBox(width: 8),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.wifi_off, size: 14, color: cook.cookOffline),
                const SizedBox(width: 2),
                Text(
                  'Offline',
                  style: TextStyle(fontSize: 11, color: cook.cookOffline),
                ),
              ],
            ),
          ],
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: cook.cookSurfaceDim,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.schedule, size: 16, color: cook.cookOnSurface),
                const SizedBox(width: 4),
                Text(
                  _formatDuration(
                    Duration(milliseconds: _restoredElapsedMs) +
                        _cookingStopwatch.elapsed,
                  ),
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: cook.cookOnSurface,
                    fontFeatures: const [FontFeature.tabularFigures()],
                    // FontFeature is from package:flutter/painting.dart,
                    // re-exported by material.dart.
                  ),
                ),
              ],
            ),
          ),
          PopupMenuButton<String>(
            icon: Icon(Icons.more_vert, color: cook.cookOnSurface),
            tooltip: 'More',
            onSelected: (value) {
              if (value == 'reset') _confirmAndResetCook();
              if (value == 'finish_now') _finishCookingEarly();
            },
            itemBuilder: (_) => const [
              PopupMenuItem<String>(
                value: 'reset',
                child: Text('Reset cook'),
              ),
              PopupMenuItem<String>(
                value: 'finish_now',
                child: Text('Finish cooking now'),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildPartialLoadBanner(
      BuildContext context, CookModeTheme cook, CookPlan plan) {
    final failed = [
      for (final c in plan.components)
        if (c.loadFailed) c,
    ];
    final headline = failed.length == 1
        ? "${failed.first.name} couldn't load — some steps may be unavailable"
        : "${failed.length} components couldn't load";
    return Container(
      key: const Key('meal_cook_partial_load_banner'),
      width: double.infinity,
      color: cook.cookError.withValues(alpha: 0.18),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          Icon(Icons.warning_amber_rounded,
              color: cook.cookError, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              headline,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w500,
                color: cook.cookOnSurface,
              ),
            ),
          ),
          TextButton(
            onPressed: () {
              // Coalesced retry — _retryComponent guards against
              // double-fire via `_retryingRecipeIds` and each completion
              // patches its own slot in `_rawRecipes`, so peer in-flight
              // retries don't corrupt each other's state.
              for (final c in failed) {
                _retryComponent(c.recipeId);
              }
            },
            child: Text(
              'Retry',
              style: TextStyle(
                color: cook.cookAccent,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStepContent(
    BuildContext context,
    CookModeTheme cook,
    CookPlan plan,
    int componentIndex,
    int stepIndex,
    CookComponent currentComponent,
  ) {
    if (currentComponent.steps.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(
            'No instructions available for this component.',
            style: TextStyle(color: cook.cookOnSurface),
            textAlign: TextAlign.center,
          ),
        ),
      );
    }
    final step = currentComponent.steps[stepIndex];
    if (currentComponent.loadFailed && isLoadFailedStep(step)) {
      return SingleChildScrollView(
        child: ComponentLoadPlaceholder(
          componentName: currentComponent.name,
          isRetrying: _retryingRecipeIds.contains(currentComponent.recipeId),
          onRetry: () => _retryComponent(currentComponent.recipeId),
        ),
      );
    }
    final timers = step.timers.isNotEmpty
        ? step.timers
        : extractTimers(step.instruction);
    final activeTotal = currentComponent.steps.length;
    final progress =
        activeTotal == 0 ? 0.0 : (stepIndex + 1) / activeTotal;
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
      child: Column(
        children: [
          // cmmrf-4 — progress bar scoped to the active recipe. The
          // numeric "{cur+1} / {total}" label sits right of the bar
          // so users always have a discrete read on their position
          // within the current recipe.
          // cmlp-5: horizontal margin 24 aligns with the step card's
          // 24dp content padding.
          Row(
            children: [
              Expanded(
                child: Container(
                  height: 4,
                  margin: const EdgeInsets.only(left: 24, right: 12),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(2),
                    child: LinearProgressIndicator(
                      value: progress,
                      backgroundColor: cook.cookSurfaceDim,
                      color: cook.cookProgress,
                    ),
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.only(right: 24),
                child: Text(
                  '${stepIndex + 1} / $activeTotal',
                  key: const Key('meal_cook_progress_label'),
                  style: TextStyle(
                    fontSize: 12,
                    color: cook.cookOnSurface,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 32),
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: cook.cookSurfaceDim,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: cook.cookDivider),
            ),
            child: Text(
              step.instruction,
              style: TextStyle(
                fontSize: 24,
                height: 1.5,
                color: cook.cookOnSurface,
              ),
              textAlign: TextAlign.center,
            ),
          ),
          if (timers.isNotEmpty) ...[
            const SizedBox(height: 24),
            StepTimersRow(
              timers: timers,
              onStart: (duration, label) => _startTimer(duration, label),
            ),
          ],
        ],
      ),
    );
  }

  void _showTimerDetailSheet(_ActiveTimer timer) {
    showModalBottomSheet(
      context: context,
      backgroundColor: context.cookModeTheme.cookSurface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (sheetContext) {
        final cook = context.cookModeTheme;
        return Padding(
          padding: const EdgeInsets.fromLTRB(24, 20, 24, 36),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                timer.label,
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: cook.cookOnSurface,
                ),
              ),
              const SizedBox(height: 16),
              Text(
                _formatDuration(timer.remaining),
                style: TextStyle(
                  fontSize: 56,
                  fontWeight: FontWeight.w700,
                  color: cook.cookTimer,
                ),
              ),
              const SizedBox(height: 24),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () {
                        Navigator.of(sheetContext).pop();
                        _cancelTimer(timer);
                      },
                      child: const Text('Cancel'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: FilledButton(
                      onPressed: () {
                        Navigator.of(sheetContext).pop();
                        _restartTimer(timer);
                      },
                      child: const Text('Restart'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }
}

class _ActiveTimer extends ActiveTimerView {
  final DateTime startTime;
  final int notifId;
  /// cmmrf-2 — the recipe id that was active when this timer was
  /// created. Persisted in [SavedTimerState.sourceRecipeId] and read
  /// by cmmrf-6 to build the `{RecipeName} · {MM:SS}` chip prefix and
  /// the completion-snackbar copy. Null on recipe-mode AND on
  /// v1-restored meal-mode timers (chip renders prefixless — honesty
  /// over guessing).
  final String? sourceRecipeId;
  Timer? timer;

  _ActiveTimer({
    required super.label,
    required super.duration,
    required super.remaining,
    required this.startTime,
    required this.notifId,
    this.sourceRecipeId,
  });
}
