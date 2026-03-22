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
import '../../../core/services/cook_timer_notification_service.dart';
import '../../../core/services/recipe_cache_service.dart';
import '../../../core/theme/theme.dart';
import 'widgets/cook_mode_chat_sheet.dart';
import 'widgets/ingredient_strip.dart';
import 'widgets/post_cook_feedback_sheet.dart';
import 'widgets/step_navigator.dart';

class CookModeScreen extends StatefulWidget {
  final String recipeId;

  const CookModeScreen({super.key, required this.recipeId});

  @override
  State<CookModeScreen> createState() => _CookModeScreenState();
}

class _CookModeScreenState extends State<CookModeScreen>
    with WidgetsBindingObserver {
  final _apiClient = getIt<ApiClient>();
  final _timerNotifService = getIt<CookTimerNotificationService>();
  final _recipeCache = getIt<RecipeCacheService>();

  Map<String, dynamic>? _recipe;
  List<dynamic> _ingredients = [];
  List<String> _steps = [];
  bool _isLoading = true;
  bool _isOffline = false;
  String? _error;

  int _currentStep = 0;
  final Set<int> _completedSteps = {};
  final Set<int> _checkedIngredients = {};

  // Timers
  final List<_ActiveTimer> _activeTimers = [];
  Timer? _timerTick;
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
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _disableWakelock();
    _timerTick?.cancel();
    _cookingStopwatch.stop();
    for (final timer in _activeTimers) {
      timer.timer?.cancel();
      _timerNotifService.cancelTimerNotification(timer.notifId);
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
        await _apiClient.addRecipeNote(
          note['recipe_id'] as String,
          note['body'] as String,
        );
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
          .map((s) => s['instruction'] as String? ?? '')
          .where((s) => s.isNotEmpty)
          .toList();
      _isLoading = false;
    });
  }

  void _goToStep(int step) {
    if (step >= 0 && step < _steps.length) {
      HapticFeedback.selectionClick();
      setState(() {
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
    );

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
    setState(() => _activeTimers.remove(timer));
  }

  void _restartTimer(_ActiveTimer timer) {
    // Cancel existing and start fresh with same label/duration
    timer.timer?.cancel();
    _timerNotifService.cancelTimerNotification(timer.notifId);
    setState(() => _activeTimers.remove(timer));
    _startTimer(timer.duration, timer.label);
  }

  void _onTimerComplete(_ActiveTimer timer) {
    HapticFeedback.heavyImpact();
    // Cancel the OS notification in case the timer fired in-app
    _timerNotifService.cancelTimerNotification(timer.notifId);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Timer done: ${timer.label}'),
        backgroundColor: context.appColors.success,
        behavior: SnackBarBehavior.floating,
      ),
    );
    setState(() {
      _activeTimers.remove(timer);
    });
  }

  String _buildRecipeContext() {
    final buf = StringBuffer();
    buf.writeln('Recipe: ${_recipe?['name'] ?? 'Unknown'}');
    if (_recipe?['servings'] != null) {
      buf.writeln('Servings: ${_recipe!['servings']}');
    }
    buf.writeln();
    buf.writeln('Ingredients:');
    for (final ing in _ingredients) {
      final qty = ing['quantity_display'] ?? '';
      final unit = ing['unit_display'] ?? '';
      final name = (ing['ingredient'] as Map?)?['canonical_name'] ?? ing['name'] ?? ing['original_text'] ?? '';
      final notes = ing['notes'] as String? ?? '';
      final line = '$qty $unit $name'.trim();
      buf.writeln('- $line${notes.isNotEmpty ? ' ($notes)' : ''}');
    }
    buf.writeln();
    buf.writeln('Steps:');
    for (var i = 0; i < _steps.length; i++) {
      buf.writeln('${i + 1}. ${_steps[i]}');
    }
    if (_steps.isNotEmpty) {
      buf.writeln();
      buf.writeln('Currently on step ${_currentStep + 1} of ${_steps.length}.');
    }
    return buf.toString();
  }

  void _showAIChatSheet() {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => CookModeChatSheet(
        recipeId: widget.recipeId,
        recipeName: _recipe?['name'] as String? ?? 'Recipe',
        recipeContext: _buildRecipeContext(),
      ),
    );
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
      backgroundColor: Theme.of(context).colorScheme.surfaceContainerLow,
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
      backgroundColor: Theme.of(context).colorScheme.surfaceContainerLow,
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
    final darkTheme = AppTheme.dark;
    return Theme(
      data: darkTheme,
      child: Builder(
        builder: (context) {
          final colorScheme = Theme.of(context).colorScheme;

          if (_isLoading) {
            return Scaffold(
              backgroundColor: colorScheme.primary,
              body: Center(
                child: CircularProgressIndicator(color: colorScheme.onSurface),
              ),
            );
          }

          if (_error != null) {
            return Scaffold(
              backgroundColor: colorScheme.primary,
              appBar: AppBar(
                backgroundColor: colorScheme.primary,
                iconTheme: IconThemeData(color: colorScheme.onSurface),
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
                          color: colorScheme.error.withValues(alpha: 0.2),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(
                          _error!,
                          style: TextStyle(color: colorScheme.onSurface),
                          textAlign: TextAlign.center,
                        ),
                      ),
                      const SizedBox(height: 16),
                      ElevatedButton(
                        onPressed: _loadRecipe,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: colorScheme.onSurface,
                          foregroundColor: colorScheme.primary,
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
            backgroundColor: colorScheme.primary,
            body: SafeArea(
              child: Column(
                children: [
                  // Header
                  _buildHeader(context, colorScheme),

                  // Active timers (if any)
                  if (_activeTimers.isNotEmpty) _buildActiveTimers(colorScheme),

                  // Ingredient strip
                  IngredientStrip(
                    ingredients: _ingredients,
                    checkedIndices: _checkedIngredients,
                    onToggle: _toggleIngredient,
                  ),

                  // Divider
                  Divider(height: 1, color: colorScheme.primaryContainer),

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
                      child: _buildStepContent(context, colorScheme),
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
        },
      ),
    );
  }

  Widget _buildHeader(BuildContext context, ColorScheme colorScheme) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      color: colorScheme.primary,
      child: Row(
        children: [
          // Back button
          IconButton(
            icon: Icon(Icons.arrow_back, color: colorScheme.onSurface),
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
                color: colorScheme.onSurface,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),

          // AI chat button (only when online)
          if (!_isOffline)
            IconButton(
              icon: Icon(Icons.chat_bubble_outline,
                  color: colorScheme.onSurface),
              onPressed: _showAIChatSheet,
              constraints: const BoxConstraints(minWidth: 64, minHeight: 64),
              padding: EdgeInsets.zero,
              tooltip: 'Ask AI',
            ),

          // Offline indicator (subtle — not alarming)
          if (_isOffline) ...[
            const SizedBox(width: 8),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.wifi_off, size: 14, color: colorScheme.tertiary),
                const SizedBox(width: 2),
                Text(
                  'Offline',
                  style: TextStyle(fontSize: 11, color: colorScheme.tertiary),
                ),
              ],
            ),
          ],

          // Cooking time
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: colorScheme.surfaceContainerLow,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.schedule, size: 16, color: colorScheme.onSurface),
                const SizedBox(width: 4),
                Text(
                  _formatDuration(_cookingStopwatch.elapsed),
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: colorScheme.onSurface,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
                ),
              ],
            ),
          ),

          // Close button
          IconButton(
            icon: Icon(Icons.close, color: colorScheme.onSurface),
            onPressed: _exitCookMode,
            constraints: const BoxConstraints(minWidth: 64, minHeight: 64),
            padding: EdgeInsets.zero,
          ),
        ],
      ),
    );
  }

  Widget _buildActiveTimers(ColorScheme colorScheme) {
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
                color: colorScheme.tertiary.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(22),
                border: Border.all(color: colorScheme.tertiary),
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
                      color: colorScheme.tertiary,
                      backgroundColor:
                          colorScheme.tertiary.withValues(alpha: 0.2),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    _formatDuration(timer.remaining),
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: colorScheme.tertiary,
                      fontFeatures: const [FontFeature.tabularFigures()],
                    ),
                  ),
                  const SizedBox(width: 4),
                  GestureDetector(
                    onTap: () => _cancelTimer(timer),
                    child: Icon(Icons.close,
                        size: 16, color: colorScheme.tertiary),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildStepContent(BuildContext context, ColorScheme colorScheme) {
    if (_steps.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(
            'No instructions available for this recipe.',
            style: TextStyle(color: colorScheme.onSurface),
            textAlign: TextAlign.center,
          ),
        ),
      );
    }

    final step = _steps[_currentStep];
    final isCompleted = _completedSteps.contains(_currentStep);
    final appColors = context.appColors;

    // Detect time mentions for inline timers
    final timePattern = RegExp(
        r'(\d+)\s*(min(?:ute)?s?|sec(?:ond)?s?|hour?s?)',
        caseSensitive: false);
    final timeMatch = timePattern.firstMatch(step);

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
                  color: colorScheme.onSurface,
                ),
              ),
              const SizedBox(width: 6),
              Text(
                'of ${_steps.length}',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                  color: colorScheme.surface,
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
                backgroundColor: colorScheme.surfaceContainerLow,
                color: colorScheme.onSurface,
              ),
            ),
          ),
          const SizedBox(height: 32),

          // Step text
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: isCompleted
                  ? appColors.success.withValues(alpha: 0.15)
                  : colorScheme.surfaceContainerLow,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: isCompleted ? appColors.success : colorScheme.primaryContainer,
              ),
            ),
            child: Column(
              children: [
                // Completed checkmark
                if (isCompleted) ...[
                  Icon(Icons.check_circle,
                      color: appColors.success, size: 32),
                  const SizedBox(height: 16),
                ],

                // Instruction text
                Text(
                  step,
                  style: TextStyle(
                    fontSize: 24,
                    height: 1.5,
                    color: isCompleted
                        ? colorScheme.onSurface.withValues(alpha: 0.6)
                        : colorScheme.onSurface,
                    decoration: isCompleted ? TextDecoration.lineThrough : null,
                  ),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),

          // Inline timer button (if time detected)
          if (timeMatch != null && !isCompleted) ...[
            const SizedBox(height: 24),
            _buildInlineTimer(timeMatch, colorScheme),
          ],

          // Swipe hint
          const SizedBox(height: 32),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.swipe, size: 16,
                  color: colorScheme.onSurface.withValues(alpha: 0.4)),
              const SizedBox(width: 8),
              Text(
                'Swipe left/right to navigate',
                style: TextStyle(
                  fontSize: 12,
                  color: colorScheme.onSurface.withValues(alpha: 0.4),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildInlineTimer(RegExpMatch match, ColorScheme colorScheme) {
    final value = int.parse(match.group(1)!);
    final unit = match.group(2)!.toLowerCase();

    Duration duration;
    if (unit.startsWith('sec')) {
      duration = Duration(seconds: value);
    } else if (unit.startsWith('hour')) {
      duration = Duration(hours: value);
    } else {
      duration = Duration(minutes: value);
    }

    return OutlinedButton.icon(
      onPressed: () => _startTimer(duration, 'Step ${_currentStep + 1}'),
      icon: const Icon(Icons.timer),
      label: Text('Set $value $unit timer'),
      style: OutlinedButton.styleFrom(
        foregroundColor: colorScheme.tertiary,
        side: BorderSide(color: colorScheme.tertiary),
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
    final colorScheme = Theme.of(context).colorScheme;
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
              color: colorScheme.onSurface.withValues(alpha: 0.3),
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
              color: colorScheme.onSurface,
            ),
          ),
          const SizedBox(height: 16),

          // Large countdown
          Text(
            widget.formatDuration(display),
            style: TextStyle(
              fontSize: 72,
              fontWeight: FontWeight.w700,
              color: colorScheme.tertiary,
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
                    foregroundColor: colorScheme.onSurface,
                    side: BorderSide(
                        color:
                            colorScheme.onSurface.withValues(alpha: 0.5)),
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
                    backgroundColor: colorScheme.tertiary,
                    foregroundColor: colorScheme.onSurface,
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
