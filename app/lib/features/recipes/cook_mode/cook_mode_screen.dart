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
    _loadRecipe();
    _enableWakelock();
    _cookingStopwatch.start();
    _startTimerTick();
    _loadTimerCategoryPref();
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
    }
  }

  void _nextStep() {
    _completedSteps.add(_currentStep);
    if (_currentStep < _steps.length - 1) {
      _goToStep(_currentStep + 1);
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
  }

  void _startTimer(Duration duration, String label) {
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
  }

  void _cancelTimer(_ActiveTimer timer) {
    timer.timer?.cancel();
    _timerNotifService.cancelTimerNotification(timer.notifId);
    _liveActivityService.endTimerActivity(timer.notifId);
    setState(() => _activeTimers.remove(timer));
    _maybeStopLiveActivityPulse();
  }

  void _restartTimer(_ActiveTimer timer) {
    // Cancel existing and start fresh with same label/duration
    timer.timer?.cancel();
    _timerNotifService.cancelTimerNotification(timer.notifId);
    _liveActivityService.endTimerActivity(timer.notifId);
    setState(() => _activeTimers.remove(timer));
    _startTimer(timer.duration, timer.label);
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
        onComplete: () => Navigator.of(sheetContext).pop(),
      ),
    );
    if (mounted) context.pop(); // Exit cook mode screen after sheet closes
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
                  _formatDuration(_cookingStopwatch.elapsed),
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
  Timer? timer;

  // ignore: unused_element_parameter
  _ActiveTimer({
    required this.label,
    required this.duration,
    required this.remaining,
    required this.startTime,
    required this.notifId,
    this.timer,
  });
}
