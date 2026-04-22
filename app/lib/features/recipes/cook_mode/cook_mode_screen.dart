import 'dart:async';
import 'dart:ui';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:wakelock_plus/wakelock_plus.dart';
import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../providers/recipe_provider.dart';
import '../../../core/services/cook_timer_notification_service.dart';
import '../../../core/services/live_activity_service.dart';
import '../../../core/services/recipe_cache_service.dart';
import '../../../core/theme/theme.dart';
import 'services/cook_session_debouncer.dart';
import 'services/cook_session_persister.dart';
import 'widgets/cook_reset_confirm_sheet.dart';
import 'widgets/cook_resume_gate_sheet.dart';
import 'widgets/timer_completion_overlay.dart';
import 'widgets/ingredient_strip.dart';
import 'widgets/manual_timer_sheet.dart';
import 'widgets/post_cook_feedback_sheet.dart';
import 'widgets/step_navigator.dart';
import 'widgets/step_timers_row.dart';
import 'util/timer_regex.dart';
import '../../../core/services/error_reporter.dart';
import '../../../shared/widgets/error_banner.dart';

class CookModeScreen extends StatefulWidget {
  final String recipeId;
  final double scaleFactor;

  const CookModeScreen({super.key, required this.recipeId, this.scaleFactor = 1.0});

  @override
  State<CookModeScreen> createState() => _CookModeScreenState();
}

class _CookModeScreenState extends State<CookModeScreen>
    with WidgetsBindingObserver {
  final _apiClient = getIt<ApiClient>();
  final _timerNotifService = getIt<CookTimerNotificationService>();
  final _liveActivityService = getIt<LiveActivityService>();
  final _recipeCache = getIt<RecipeCacheService>();

  Map<String, dynamic>? _recipe;
  List<dynamic> _ingredients = [];
  List<_StepData> _steps = [];
  bool _isLoading = true;
  bool _isOffline = false;
  String? _error;
  String? _errorDetail;

  int _currentStep = 0;
  final Set<int> _completedSteps = {};
  final Set<int> _checkedIngredients = {};

  // Persisted-resume bookkeeping (epic-cook-mode-resume). A Stopwatch
  // cannot be seeded to a baseline; instead we stash prior elapsed
  // milliseconds here and display `baseline + stopwatch.elapsed`.
  // Assigned on the Resume path in cmr-3.
  // ignore: prefer_final_fields
  int _restoredElapsedMs = 0;
  int? _startedAtMs;
  late final CookSessionPersister _persister;
  late final CookSessionDebouncer _debouncer;
  String get _sessionKey => CookSessionKey.forRecipe(widget.recipeId);

  // Per-category notification pref (timer-3). Null until the one-shot
  // fetch resolves; callers treat null as "assume true" so the overlay
  // appears on first-run / offline paths.
  bool? _timerCategoryEnabled;

  // Timers
  final List<_ActiveTimer> _activeTimers = [];
  Timer? _timerTick;
  // Minute-cadence pump that re-anchors `endTime` on every active Live
  // Activity. Created lazily when the first timer starts and torn down
  // when the last timer clears.
  Timer? _liveActivityPulse;
  int _nextNotifId = 0;

  // Total cooking time tracker
  final Stopwatch _cookingStopwatch = Stopwatch();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _persister = CookSessionPersister();
    _debouncer = CookSessionDebouncer(_persister);
    _enableWakelock();
    _startTimerTick();
    _loadTimerCategoryPref();
    // cmr-2: stopwatch start is deferred until after the persisted-state
    // resolution runs. cmr-3 adds the Resume / Start Over gate between
    // these two points; for cmr-2 any prior state is discarded.
    _initCookSession();
  }

  /// Resolve any persisted session and start the live stopwatch.
  ///
  /// Ordering is load-bearing:
  ///   1. Load persisted state (may be null).
  ///   2. Fetch the recipe so the gate has the name + total step count.
  ///   3. If recipe load failed or yielded zero steps, skip the gate —
  ///      the error / empty-state UI takes over.
  ///   4. If persisted state exists, show the Resume / Start Over gate.
  ///   5. Only after the gate resolves (or no gate was shown) do we
  ///      start the cooking stopwatch — otherwise the restored
  ///      `cumulative_elapsed_ms` drifts during the load + gate window.
  Future<void> _initCookSession() async {
    final persisted = await _persister.load(_sessionKey);
    if (!mounted) return;
    await _loadRecipe();
    if (!mounted) return;
    if (persisted != null && _error == null && _steps.isNotEmpty) {
      final targetName = _recipe?['name'] as String? ?? widget.recipeId;
      final choice = await showCookResumeGate(
        context,
        state: persisted,
        targetName: targetName,
        totalSteps: _steps.length,
      );
      if (!mounted) return;
      if (choice == CookResumeChoice.resume) {
        _applyRestoredState(persisted);
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

  /// Populate in-memory state from a persisted [state] snapshot.
  /// Steps + ingredients beyond the current recipe's shape are clamped
  /// silently (Path E of the epic — recipe edited since last session);
  /// a one-shot snackbar explains the shift. Timers whose deadlines
  /// are already past are NOT added back; their labels are surfaced
  /// in a "while you were away" snackbar (cmr-5).
  void _applyRestoredState(CookSessionState state) {
    final totalSteps = _steps.length;
    int restoredStep = state.currentStep;
    bool clamped = false;
    if (restoredStep >= totalSteps) {
      restoredStep = totalSteps - 1;
      clamped = true;
    }
    if (restoredStep < 0) restoredStep = 0;
    final validCompleted = state.completedSteps
        .where((i) => i >= 0 && i < totalSteps)
        .toSet();
    final ingredientCount = _ingredients.length;
    final validChecked = <int>{};
    for (final raw in state.checkedIngredients) {
      final idx = int.tryParse(raw);
      if (idx != null && idx >= 0 && idx < ingredientCount) {
        validChecked.add(idx);
      }
    }

    // cmr-5: rebuild timers. Absolute deadline_ms lets us compute
    // remaining without caring how long the app was backgrounded.
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
        source: saved.source,
      );
      // Re-schedule OS notification at the original deadline so the
      // alert fires whether or not the app is foregrounded. Idempotent
      // from the OS's perspective — if a phantom notification survived
      // the kill, rescheduling at the same time is a no-op.
      _timerNotifService.scheduleTimerNotification(
        id: notifId,
        label: saved.label,
        expiresAt: DateTime.fromMillisecondsSinceEpoch(saved.deadlineMs),
        recipeId: widget.recipeId,
        stepIndex: restoredStep,
        originalDurationSeconds: saved.totalDurationSeconds,
      );
      // Live Activities are OS-ephemeral — the kill disposed them.
      // Resume intentionally does NOT restart them. A new timer started
      // post-Resume gets a fresh activity via _startTimer.
      timer.timer = Timer.periodic(const Duration(seconds: 1), (t) {
        if (!mounted) return;
        final elapsed = DateTime.now().difference(timer.startTime);
        final remaining = timer.duration - elapsed;
        if (remaining.isNegative) {
          t.cancel();
          _onTimerComplete(timer);
        } else {
          setState(() {
            timer.remaining = remaining;
          });
        }
      });
      restoredTimers.add(timer);
    }

    setState(() {
      _currentStep = restoredStep;
      _completedSteps
        ..clear()
        ..addAll(validCompleted);
      _checkedIngredients
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
            'Recipe changed since your last session — picking up at the last step',
          ),
          duration: Duration(seconds: 4),
        ),
      );
    }
    if (expiredWhileAway.isNotEmpty && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(_expiredAwayCopy(expiredWhileAway)),
          duration: const Duration(seconds: 5),
          action: SnackBarAction(
            label: 'OK',
            onPressed: () {},
          ),
        ),
      );
    }
  }

  /// Compose the "while you were away" snackbar body. 1 label →
  /// singular; 2–3 labels → comma list with Oxford "and"; 4+ →
  /// consolidated count.
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

  /// Fire-and-forget read of the user's per-category notification prefs.
  /// If the user has explicitly set `categories.timers == false`, the
  /// in-app timer-completion overlay is suppressed (the OS alarm still
  /// fires — that's a system-level signal). A failure / missing value
  /// leaves `_timerCategoryEnabled` null, which the call site treats as
  /// "assume true".
  Future<void> _loadTimerCategoryPref() async {
    try {
      final response = await _apiClient.getNotificationPreferences();
      if (!mounted) return;
      final data = response.data as Map<String, dynamic>;
      final categories = data['categories'];
      if (categories is Map && categories['timers'] is bool) {
        setState(() => _timerCategoryEnabled = categories['timers'] as bool);
      }
    } catch (_) {
      // Silently ignore — leave null so the overlay defaults to showing.
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    // Belt-and-suspenders flush. The primary flush is
    // `AppLifecycleState.paused` — dispose can fire after the OS
    // already killed the process. Fire-and-forget: we can't await in
    // dispose and the save is idempotent.
    unawaited(_debouncer.flushNow());
    _disableWakelock();
    _timerTick?.cancel();
    _liveActivityPulse?.cancel();
    _cookingStopwatch.stop();
    for (final timer in _activeTimers) {
      timer.timer?.cancel();
      _timerNotifService.cancelTimerNotification(timer.notifId);
      // End the lock-screen / Dynamic Island activity so it doesn't
      // linger after the user exits cook mode.
      _liveActivityService.endTimerActivity(timer.notifId);
    }
    super.dispose();
  }

  /// Reconcile timer countdowns after the app returns from background,
  /// and attempt to sync any pending offline note additions.
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // cmr-2: flush pending session writes before the OS potentially
    // kills the process. `paused` is the reliable signal; `dispose`
    // fires too late in kill scenarios. Safe to call unconditionally
    // — flushNow is a no-op when nothing is pending.
    if (state == AppLifecycleState.paused) {
      unawaited(_debouncer.flushNow());
    }
    if (state == AppLifecycleState.resumed && mounted) {
      final now = DateTime.now();
      final expired = <_ActiveTimer>[];
      // Batch all remaining updates into a single setState to avoid per-timer rebuilds
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
      _syncPendingNotes();
    }
  }

  /// Attempts to sync queued offline note additions when connectivity is restored.
  /// Also clears the offline indicator as soon as connectivity is confirmed.
  /// Silently no-ops on failure — will retry on next app resume.
  Future<void> _syncPendingNotes() async {
    try {
      final results = await Connectivity().checkConnectivity();
      if (results.contains(ConnectivityResult.none)) return;

      // Connectivity confirmed — clear offline indicator regardless of pending notes
      if (mounted && _isOffline) {
        setState(() => _isOffline = false);
      }

      final pending = await _recipeCache.getPendingNotes();
      if (pending.isEmpty) return;

      // All-or-nothing sync: if any note fails, the whole batch stays queued
      // and retries on next resume. Known trade-off: no partial-success clearing.
      for (final note in pending) {
        final recipeId = note['recipe_id'] as String;
        await _apiClient.addRecipeNote(
          recipeId,
          note['body'] as String,
        );
        // pfc-3: drop the cached recipe payload so the detail screen
        // refetches with the newly-appended note.
        if (mounted) invalidateRecipe(context, recipeId);
      }
      await _recipeCache.clearPendingNotes();
    } catch (_) {
      // Silently ignore — will retry on next resume
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
      // Only rebuild when timer display values need updating
      if (_activeTimers.isNotEmpty || _cookingStopwatch.isRunning) {
        setState(() {});
      }
    });
  }

  Future<void> _loadRecipe() async {
    try {
      final response = await _apiClient.getRecipe(widget.recipeId);
      // Cache on successful fetch so subsequent offline loads work
      await _recipeCache.cacheRecipe(
          widget.recipeId, response.data as Map<String, dynamic>);
      if (mounted) {
        _populateFromData(response.data as Map<String, dynamic>);
      }
    } on DioException catch (e) {
      if (_isNetworkError(e)) {
        final cached = await _recipeCache.loadCachedRecipe(widget.recipeId);
        if (cached != null && mounted) {
          setState(() => _isOffline = true);
          _populateFromData(cached);
          return;
        }
        if (mounted) {
          setState(() {
            _error = 'No cached data. Connect to internet and retry.';
            _isLoading = false;
          });
        }
      } else {
        if (mounted) {
          setState(() {
            _error = 'Failed to load recipe: $e';
            _isLoading = false;
          });
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Failed to load recipe: $e';
          _errorDetail = ErrorReporter.detail(e);
          _isLoading = false;
        });
      }
    }
  }

  bool _isNetworkError(DioException e) {
    return e.type == DioExceptionType.connectionError ||
        e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.sendTimeout ||
        e.type == DioExceptionType.receiveTimeout;
  }

  void _populateFromData(Map<String, dynamic> recipe) {
    final stepsData = List<dynamic>.from(recipe['steps'] as List? ?? []);
    stepsData.sort((a, b) =>
        (a['step_number'] as int? ?? 0).compareTo(b['step_number'] as int? ?? 0));
    setState(() {
      _recipe = recipe;
      _ingredients = recipe['ingredients'] ?? [];
      _steps = stepsData
          .map((s) => _StepData.fromJson(s))
          .where((s) => s.instruction.isNotEmpty)
          .toList();
      _isLoading = false;
    });
  }

  void _goToStep(int step) {
    if (step >= 0 && step < _steps.length) {
      HapticFeedback.selectionClick();
      setState(() {
        // When the user navigates backward we untoggle the destination
        // step's "completed" state so returning to a prior step renders
        // it as in-progress, not crossed out. Forward nav keeps adding
        // via _nextStep. Covers swipe, tap-zone, and pill-tap routes
        // (cmp-4 AC8).
        if (step < _currentStep) {
          _completedSteps.remove(step);
        }
        _currentStep = step;
      });
      _persistState();
    }
  }

  void _nextStep() {
    _completedSteps.add(_currentStep);
    if (_currentStep < _steps.length - 1) {
      _goToStep(_currentStep + 1);
    } else {
      _persistState();
    }
  }

  void _previousStep() {
    _goToStep(_currentStep - 1);
  }

  void _markAllUpToHere() {
    HapticFeedback.mediumImpact();
    setState(() {
      for (int i = 0; i <= _currentStep; i++) {
        _completedSteps.add(i);
      }
    });
    _persistState();
  }

  void _toggleIngredient(int index) {
    HapticFeedback.selectionClick();
    setState(() {
      if (_checkedIngredients.contains(index)) {
        _checkedIngredients.remove(index);
      } else {
        _checkedIngredients.add(index);
      }
    });
    _persistState();
  }

  void _startTimer(Duration duration, String label, {String source = 'manual'}) {
    HapticFeedback.mediumImpact();

    final notifId = _nextNotifId++;
    final startTime = DateTime.now();
    final expiresAt = startTime.add(duration);

    final activeTimer = _ActiveTimer(
      label: label,
      duration: duration,
      remaining: duration,
      startTime: startTime,
      notifId: notifId,
      source: source,
    );

    // Schedule OS-level notification so timer fires even when app is suspended
    _timerNotifService.scheduleTimerNotification(
      id: notifId,
      label: label,
      expiresAt: expiresAt,
      recipeId: widget.recipeId,
      stepIndex: _currentStep,
      originalDurationSeconds: duration.inSeconds,
    );

    // Start a Live Activity so the lock-screen banner + Dynamic Island
    // countdown appear immediately (iOS only; no-op elsewhere).
    _liveActivityService.startTimerActivity(
      notifId: notifId,
      timerLabel: label,
      recipeName: _recipe?['name'] as String? ?? 'Recipe',
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

    setState(() {
      _activeTimers.add(activeTimer);
    });
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
    // Cancel existing and start fresh with same label/duration
    timer.timer?.cancel();
    _timerNotifService.cancelTimerNotification(timer.notifId);
    _liveActivityService.endTimerActivity(timer.notifId);
    setState(() => _activeTimers.remove(timer));
    _startTimer(timer.duration, timer.label, source: timer.source);
  }

  void _onTimerComplete(_ActiveTimer timer) {
    HapticFeedback.heavyImpact();
    // Cancel the OS notification in case the timer fired in-app
    _timerNotifService.cancelTimerNotification(timer.notifId);
    // Flip the Live Activity to the "Done!" state; Swift side auto-
    // dismisses after 5 minutes.
    _liveActivityService.completeTimerActivity(timer.notifId);
    if (!mounted) return;

    // Remove the expired timer from state before surfacing UI —
    // drag-down dismiss, action callbacks, and the SnackBar fallback
    // all assume the timer is no longer "active".
    setState(() {
      _activeTimers.remove(timer);
    });
    _maybeStopLiveActivityPulse();
    _persistState();

    // timer-3: show the cook-mode completion overlay unless the user
    // has explicitly turned timer notifications off. Null = not yet
    // fetched or fetch failed → default to showing (epic-level
    // "acceptable lag" decision).
    final gated = _timerCategoryEnabled == false;
    if (!gated) {
      showTimerCompletionOverlay(
        context: context,
        label: timer.label,
        recipeName: _recipe?['name'] as String?,
        stepNumber: _currentStep,
        onAdd2: () => _extendExpiredTimer(timer, 2),
        onAdd5: () => _extendExpiredTimer(timer, 5),
        onReset: () => _startTimer(timer.duration, timer.label),
        onStop: () {}, // no-op — the timer is already removed
      );
    } else {
      final cook = context.cookModeTheme;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Timer done: ${timer.label}'),
          backgroundColor: cook.cookCompleted,
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  /// Restart an expired timer with an extended duration. Preserves the
  /// original label lineage (e.g. `Bake (+2m)`) so repeat extensions
  /// stay readable.
  void _extendExpiredTimer(_ActiveTimer expired, int minutes) {
    final extendedLabel = '${expired.label} (+${minutes}m)';
    _startTimer(Duration(minutes: minutes), extendedLabel);
  }

  /// Start the minute-cadence pulse that re-anchors `endTime` on every
  /// active Live Activity. Idempotent — called every time a timer is
  /// added, but only creates the pulse when there isn't one already.
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

  /// Tear down the minute-cadence pulse once the last active timer
  /// clears, so we don't burn battery on an idle cook-mode screen.
  void _maybeStopLiveActivityPulse() {
    if (_activeTimers.isNotEmpty) return;
    _liveActivityPulse?.cancel();
    _liveActivityPulse = null;
  }

  /// Schedule a debounced snapshot write. Call from every
  /// state-mutating handler (step advance, toggle, timer add/cancel/
  /// complete). Timer-tick handlers do NOT call this — absolute
  /// `deadline_ms` doesn't drift on each tick.
  void _persistState() {
    _debouncer.markDirty(_sessionKey, _buildSnapshot);
  }

  CookSessionState _buildSnapshot() {
    final nowMs = DateTime.now().millisecondsSinceEpoch;
    _startedAtMs ??= nowMs;
    final completed = _completedSteps.toList()..sort();
    final checked = _checkedIngredients.map((i) => i.toString()).toList()
      ..sort();
    return CookSessionState(
      targetKind: CookTargetKind.recipe,
      targetId: widget.recipeId,
      startedAtMs: _startedAtMs!,
      cumulativeElapsedMs:
          _restoredElapsedMs + _cookingStopwatch.elapsedMilliseconds,
      currentStep: _currentStep,
      completedSteps: completed,
      checkedIngredients: checked,
      activeTimers: _activeTimers
          .map(
            (t) => SavedTimerState(
              label: t.label,
              deadlineMs: t.startTime.add(t.duration).millisecondsSinceEpoch,
              totalDurationSeconds: t.duration.inSeconds,
              source: t.source,
            ),
          )
          .toList(),
      updatedAtMs: nowMs,
    );
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
    final uniqueLabel = disambiguateTimerLabel(
      rawLabel,
      _activeTimers.map((t) => t.label),
    );
    _startTimer(Duration(minutes: minutes), uniqueLabel);
  }

  void _exitCookMode() {
    _cookingStopwatch.stop();
    // Mark current step as complete
    _completedSteps.add(_currentStep);
    context.pop();
  }

  void _finishCooking() {
    _completedSteps.add(_currentStep);
    HapticFeedback.heavyImpact();
    _cookingStopwatch.stop();
    _showPostCookFeedbackSheet();
  }

  Future<void> _showPostCookFeedbackSheet() async {
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
        recipeId: widget.recipeId,
        recipeName: _recipe?['name'] as String? ?? 'Recipe',
        apiClient: _apiClient,
        recipeCache: _recipeCache,
        isOffline: _isOffline,
        onComplete: ({bool saved = false}) {
          // cmr-4 AC4: clear the persisted session only when the post-cook
          // save succeeded. Skip / catch path leaves state intact so the
          // user can retry without losing their session.
          if (saved) {
            _debouncer.discardPending();
            unawaited(_persister.clear(_sessionKey));
          }
          if (sheetContext.mounted) Navigator.of(sheetContext).pop();
        },
      ),
    );
    if (mounted) context.pop(); // Exit cook mode screen after sheet closes
  }

  /// Open the overflow-menu-driven Reset confirmation sheet. On confirm:
  /// cancel every active timer + OS notification + live activity, clear
  /// persisted state, reset in-memory state, and restart the stopwatch.
  Future<void> _confirmAndResetCook() async {
    final confirmed = await showCookResetConfirmSheet(context);
    if (!confirmed || !mounted) return;
    // Cancel timers (in-memory + OS + live activity). Copy the list —
    // _cancelTimer mutates _activeTimers via setState.
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
      _currentStep = 0;
      _completedSteps.clear();
      _checkedIngredients.clear();
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

  String _formatDuration(Duration d) {
    final minutes = d.inMinutes;
    final seconds = d.inSeconds % 60;
    return '${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
  }

  void _showTimerDetailSheet(_ActiveTimer timer) {
    showModalBottomSheet(
      context: context,
      backgroundColor: context.cookModeTheme.cookSurface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (sheetContext) {
        return _TimerDetailSheet(
          timer: timer,
          formatDuration: _formatDuration,
          onCancel: () {
            Navigator.of(sheetContext).pop();
            _cancelTimer(timer);
          },
          onRestart: () {
            Navigator.of(sheetContext).pop();
            _restartTimer(timer);
          },
        );
      },
    );
  }

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

    if (_error != null) {
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
                    _error!,
                    style: TextStyle(color: cook.cookOnSurface),
                    textAlign: TextAlign.center,
                  ),
                ),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: _loadRecipe,
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

    return Scaffold(
      backgroundColor: cook.cookSurface,
      body: SafeArea(
        child: Column(
          children: [
            // Header
            _buildHeader(context, cook),

            // Active timers (if any)
            if (_activeTimers.isNotEmpty) _buildActiveTimers(cook),

            // Ingredient strip
            IngredientStrip(
              ingredients: _ingredients,
              checkedIndices: _checkedIngredients,
              onToggle: _toggleIngredient,
              scaleFactor: widget.scaleFactor,
            ),

            // Divider
            Divider(height: 1, color: cook.cookDivider),

            // Step content
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
                // Left 25% = go back, right 25% = go next, middle 50% = no-op
                // Invisible tap zones for messy-hands navigation (AC: Story 6.2)
                onTapUp: (details) {
                  final screenWidth = MediaQuery.of(context).size.width;
                  final tapX = details.localPosition.dx;
                  if (tapX < screenWidth * 0.25) {
                    if (_currentStep > 0) _previousStep();
                  } else if (tapX > screenWidth * 0.75) {
                    if (_currentStep < _steps.length - 1) _nextStep();
                  }
                },
                child: _buildStepContent(context, cook),
              ),
            ),

            // Step navigator
            StepNavigator(
              currentStep: _currentStep,
              totalSteps: _steps.length,
              completedSteps: _completedSteps,
              onPrevious: _currentStep > 0 ? _previousStep : null,
              onNext: _currentStep < _steps.length - 1 ? _nextStep : null,
              onDone: _finishCooking,
              onStepTap: _goToStep,
              onLongPressStep: _markAllUpToHere,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context, CookModeTheme cook) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      color: cook.cookSurface,
      child: Row(
        children: [
          // Back button
          IconButton(
            icon: Icon(Icons.arrow_back, color: cook.cookOnSurface),
            onPressed: _exitCookMode,
            constraints: const BoxConstraints(minWidth: 64, minHeight: 64),
            padding: EdgeInsets.zero,
          ),

          // Recipe name
          Expanded(
            child: Text(
              _recipe?['name'] ?? 'Recipe',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: cook.cookOnSurface,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),

          // cmt-5: manual timer entry is ALWAYS visible — online, offline,
          // and regardless of whether step.timers or the regex surfaced
          // anything for the current step. 48x48 tap target (AA minimum)
          // keeps the 360dp header from crushing the recipe title.
          IconButton(
            icon: Icon(Icons.timer_outlined, color: cook.cookOnSurface),
            onPressed: _showManualTimerSheet,
            constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
            padding: EdgeInsets.zero,
            tooltip: 'Add a timer',
          ),

          // Offline indicator (subtle — not alarming)
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

          // Cooking time
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
                  ),
                ),
              ],
            ),
          ),

          // Close button
          IconButton(
            icon: Icon(Icons.close, color: cook.cookOnSurface),
            onPressed: _exitCookMode,
            constraints: const BoxConstraints(minWidth: 64, minHeight: 64),
            padding: EdgeInsets.zero,
          ),

          // Overflow menu (cmr-4). Rightmost header element. Currently
          // carries a single Reset-cook entry; future affordances fold
          // into the same menu rather than spawning more icons.
          PopupMenuButton<String>(
            icon: Icon(Icons.more_vert, color: cook.cookOnSurface),
            tooltip: 'More',
            onSelected: (value) {
              if (value == 'reset') _confirmAndResetCook();
            },
            itemBuilder: (_) => const [
              PopupMenuItem<String>(
                value: 'reset',
                child: Text('Reset cook'),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildActiveTimers(CookModeTheme cook) {
    return Container(
      height: 44,
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: _activeTimers.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final timer = _activeTimers[index];
          final progress =
              1 - (timer.remaining.inSeconds / timer.duration.inSeconds);

          return GestureDetector(
            onTap: () => _showTimerDetailSheet(timer),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              decoration: BoxDecoration(
                color: cook.cookTimer.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(22),
                border: Border.all(color: cook.cookTimer),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                      value: progress,
                      strokeWidth: 2,
                      color: cook.cookTimer,
                      backgroundColor:
                          cook.cookTimer.withValues(alpha: 0.2),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    _formatDuration(timer.remaining),
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: cook.cookTimer,
                      fontFeatures: const [FontFeature.tabularFigures()],
                    ),
                  ),
                  const SizedBox(width: 4),
                  GestureDetector(
                    onTap: () => _cancelTimer(timer),
                    child: Icon(Icons.close,
                        size: 16, color: cook.cookTimer),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildStepContent(BuildContext context, CookModeTheme cook) {
    if (_steps.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(
            'No instructions available for this recipe.',
            style: TextStyle(color: cook.cookOnSurface),
            textAlign: TextAlign.center,
          ),
        ),
      );
    }

    final step = _steps[_currentStep];
    // cmt-4: hybrid is FALLBACK, not merge. Structured timers suppress
    // the regex even when the instruction mentions more durations.
    final timers = step.timers.isNotEmpty
        ? step.timers
        : extractTimers(step.instruction);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        children: [
          // Step indicator
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(
                '${_currentStep + 1}',
                style: TextStyle(
                  fontSize: 32,
                  fontWeight: FontWeight.w700,
                  color: cook.cookOnSurface,
                ),
              ),
              const SizedBox(width: 6),
              Text(
                'of ${_steps.length}',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                  color: cook.cookOnSurface.withValues(alpha: 0.6),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),

          // Progress bar
          Container(
            height: 4,
            margin: const EdgeInsets.symmetric(horizontal: 48),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(2),
              child: LinearProgressIndicator(
                value: (_currentStep + 1) / _steps.length,
                backgroundColor: cook.cookSurfaceDim,
                color: cook.cookProgress,
              ),
            ),
          ),
          const SizedBox(height: 32),

          // Step text — current step never renders with completed visuals.
          // Completed styling lives in StepNavigator pills for non-current
          // indices; see cmp-2 AC3 + cmp-4 AC5.
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

          // Inline timer buttons (extractor-supplied OR regex fallback;
          // hybrid is fallback not merge — see cmt-4 AC2).
          if (timers.isNotEmpty) ...[
            const SizedBox(height: 24),
            StepTimersRow(
              timers: timers,
              onStart: (duration, label) => _startTimer(duration, label),
            ),
          ],

          // Swipe hint
          const SizedBox(height: 32),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.swipe, size: 16,
                  color: cook.cookOnSurface.withValues(alpha: 0.4)),
              const SizedBox(width: 8),
              Text(
                'Swipe left/right to navigate',
                style: TextStyle(
                  fontSize: 12,
                  color: cook.cookOnSurface.withValues(alpha: 0.4),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

}

/// Bottom sheet showing timer detail: label, live countdown, cancel and restart.
class _TimerDetailSheet extends StatefulWidget {
  final _ActiveTimer timer;
  final String Function(Duration) formatDuration;
  final VoidCallback onCancel;
  final VoidCallback onRestart;

  const _TimerDetailSheet({
    required this.timer,
    required this.formatDuration,
    required this.onCancel,
    required this.onRestart,
  });

  @override
  State<_TimerDetailSheet> createState() => _TimerDetailSheetState();
}

class _TimerDetailSheetState extends State<_TimerDetailSheet> {
  Timer? _tick;

  @override
  void initState() {
    super.initState();
    _tick = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _tick?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cook = context.cookModeTheme;
    final elapsed =
        DateTime.now().difference(widget.timer.startTime);
    final remaining = widget.timer.duration - elapsed;
    final display =
        remaining.isNegative ? Duration.zero : remaining;

    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 20, 24, 36),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Drag handle
          Container(
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: cook.cookOnSurface.withValues(alpha: 0.3),
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(height: 20),

          // Label
          Text(
            widget.timer.label,
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: cook.cookOnSurface,
            ),
          ),
          const SizedBox(height: 16),

          // Large countdown
          Text(
            widget.formatDuration(display),
            style: TextStyle(
              fontSize: 72,
              fontWeight: FontWeight.w700,
              color: cook.cookTimer,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
          const SizedBox(height: 32),

          // Buttons
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: widget.onCancel,
                  icon: const Icon(Icons.close),
                  label: const Text('Cancel Timer'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: cook.cookOnSurface,
                    side: BorderSide(
                        color:
                            cook.cookOnSurface.withValues(alpha: 0.5)),
                    minimumSize: const Size.fromHeight(48),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: FilledButton.icon(
                  onPressed: widget.onRestart,
                  icon: const Icon(Icons.replay),
                  label: const Text('Restart'),
                  style: FilledButton.styleFrom(
                    backgroundColor: cook.cookTimer,
                    foregroundColor: cook.cookOnAccent,
                    minimumSize: const Size.fromHeight(48),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// cmt-4 — per-step record kept on `_steps`.
///
/// Prior to cmt-4, `_steps` was `List<String>`; the upgrade pulls
/// structured `timers` out of the backend payload at load time so the
/// render path doesn't re-parse the JSON on every build.
class _StepData {
  final String instruction;
  final List<StepTimer> timers;

  const _StepData({required this.instruction, required this.timers});

  factory _StepData.fromJson(dynamic raw) {
    if (raw is! Map) return const _StepData(instruction: '', timers: []);
    final instruction = raw['instruction'] as String? ?? '';
    final rawTimers = raw['timers'];
    final parsed = <StepTimer>[];
    if (rawTimers is List) {
      for (final t in rawTimers) {
        final parsedTimer = StepTimer.fromJson(t);
        if (parsedTimer != null) parsed.add(parsedTimer);
      }
    }
    return _StepData(instruction: instruction, timers: parsed);
  }
}

class _ActiveTimer {
  final String label;
  final Duration duration;
  Duration remaining;
  final DateTime startTime;
  final int notifId;
  // One of 'extracted', 'regex', 'manual' — preserved across the
  // persist / Resume boundary so restored timers look identical to the
  // ones the user originally started.
  final String source;
  Timer? timer;

  // ignore: unused_element_parameter
  _ActiveTimer({
    required this.label,
    required this.duration,
    required this.remaining,
    required this.startTime,
    required this.notifId,
    this.source = 'manual',
    this.timer,
  });
}
