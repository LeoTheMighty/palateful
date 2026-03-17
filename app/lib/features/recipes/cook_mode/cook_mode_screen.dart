import 'dart:async';
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:wakelock_plus/wakelock_plus.dart';
import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../../../core/theme/app_colors.dart';
import 'widgets/ingredient_strip.dart';
import 'widgets/step_navigator.dart';

class CookModeScreen extends StatefulWidget {
  final String recipeId;

  const CookModeScreen({super.key, required this.recipeId});

  @override
  State<CookModeScreen> createState() => _CookModeScreenState();
}

class _CookModeScreenState extends State<CookModeScreen> {
  final _apiClient = getIt<ApiClient>();

  Map<String, dynamic>? _recipe;
  List<dynamic> _ingredients = [];
  List<String> _steps = [];
  bool _isLoading = true;
  String? _error;

  int _currentStep = 0;
  final Set<int> _completedSteps = {};
  final Set<int> _checkedIngredients = {};

  // Timers
  final List<_ActiveTimer> _activeTimers = [];
  Timer? _timerTick;

  // Total cooking time tracker
  final Stopwatch _cookingStopwatch = Stopwatch();

  @override
  void initState() {
    super.initState();
    _loadRecipe();
    _enableWakelock();
    _cookingStopwatch.start();
    _startTimerTick();
  }

  @override
  void dispose() {
    _disableWakelock();
    _timerTick?.cancel();
    _cookingStopwatch.stop();
    for (final timer in _activeTimers) {
      timer.timer?.cancel();
    }
    super.dispose();
  }

  void _enableWakelock() async {
    await WakelockPlus.enable();
  }

  void _disableWakelock() async {
    await WakelockPlus.disable();
  }

  void _startTimerTick() {
    _timerTick = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
  }

  Future<void> _loadRecipe() async {
    try {
      final response = await _apiClient.getRecipe(widget.recipeId);
      if (mounted) {
        final recipe = response.data;
        setState(() {
          _recipe = recipe;
          _ingredients = recipe['ingredients'] ?? [];
          final stepsData = List<dynamic>.from(recipe['steps'] as List? ?? []);
          stepsData.sort((a, b) =>
              (a['step_number'] as int? ?? 0)
                  .compareTo(b['step_number'] as int? ?? 0));
          _steps = stepsData
              .map((s) => s['instruction'] as String? ?? '')
              .where((s) => s.isNotEmpty)
              .toList();
          _isLoading = false;
        });
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

    final activeTimer = _ActiveTimer(
      label: label,
      duration: duration,
      remaining: duration,
      startTime: DateTime.now(),
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

  void _onTimerComplete(_ActiveTimer timer) {
    HapticFeedback.heavyImpact();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Timer done: ${timer.label}'),
        backgroundColor: AppColors.success,
        behavior: SnackBarBehavior.floating,
      ),
    );
    setState(() {
      _activeTimers.remove(timer);
    });
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
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Recipe completed! Great job! 🎉'),
        backgroundColor: AppColors.success,
        behavior: SnackBarBehavior.floating,
      ),
    );
    context.pop();
  }

  String _formatDuration(Duration d) {
    final minutes = d.inMinutes;
    final seconds = d.inSeconds % 60;
    return '${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(
        backgroundColor: AppColors.chocolate,
        body: Center(
          child: CircularProgressIndicator(color: AppColors.warmIvory),
        ),
      );
    }

    if (_error != null) {
      return Scaffold(
        backgroundColor: AppColors.chocolate,
        appBar: AppBar(
          backgroundColor: AppColors.chocolate,
          iconTheme: const IconThemeData(color: AppColors.warmIvory),
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
                    color: AppColors.withOpacity(AppColors.errorDark, 0.2),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    _error!,
                    style: const TextStyle(color: AppColors.warmIvory),
                    textAlign: TextAlign.center,
                  ),
                ),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: _loadRecipe,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.warmIvory,
                    foregroundColor: AppColors.chocolate,
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
      backgroundColor: AppColors.chocolate,
      body: SafeArea(
        child: Column(
          children: [
            // Header
            _buildHeader(),

            // Active timers (if any)
            if (_activeTimers.isNotEmpty) _buildActiveTimers(),

            // Ingredient strip
            IngredientStrip(
              ingredients: _ingredients,
              checkedIndices: _checkedIngredients,
              onToggle: _toggleIngredient,
            ),

            // Divider
            const Divider(height: 1, color: AppColors.chocolateLight),

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
                child: _buildStepContent(),
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

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      color: AppColors.chocolate,
      child: Row(
        children: [
          // Back button
          IconButton(
            icon: const Icon(Icons.arrow_back, color: AppColors.warmIvory),
            onPressed: _exitCookMode,
          ),

          // Recipe name
          Expanded(
            child: Text(
              _recipe?['name'] ?? 'Recipe',
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: AppColors.warmIvory,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),

          // Cooking time
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: AppColors.chocolateDark,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.schedule, size: 16, color: AppColors.warmIvory),
                const SizedBox(width: 4),
                Text(
                  _formatDuration(_cookingStopwatch.elapsed),
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppColors.warmIvory,
                    fontFeatures: [FontFeature.tabularFigures()],
                  ),
                ),
              ],
            ),
          ),

          // Close button
          IconButton(
            icon: const Icon(Icons.close, color: AppColors.warmIvory),
            onPressed: _exitCookMode,
          ),
        ],
      ),
    );
  }

  Widget _buildActiveTimers() {
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

          return Container(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            decoration: BoxDecoration(
              color: AppColors.withOpacity(AppColors.terracotta, 0.15),
              borderRadius: BorderRadius.circular(22),
              border: Border.all(color: AppColors.terracotta),
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
                    color: AppColors.terracotta,
                    backgroundColor:
                        AppColors.withOpacity(AppColors.terracotta, 0.2),
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  _formatDuration(timer.remaining),
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppColors.terracotta,
                    fontFeatures: [FontFeature.tabularFigures()],
                  ),
                ),
                const SizedBox(width: 4),
                GestureDetector(
                  onTap: () {
                    timer.timer?.cancel();
                    setState(() => _activeTimers.remove(timer));
                  },
                  child: const Icon(Icons.close,
                      size: 16, color: AppColors.terracotta),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildStepContent() {
    if (_steps.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'No instructions available for this recipe.',
            style: TextStyle(color: AppColors.warmIvory),
            textAlign: TextAlign.center,
          ),
        ),
      );
    }

    final step = _steps[_currentStep];
    final isCompleted = _completedSteps.contains(_currentStep);

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
                style: const TextStyle(
                  fontSize: 32,
                  fontWeight: FontWeight.w700,
                  color: AppColors.warmIvory,
                ),
              ),
              const SizedBox(width: 6),
              Text(
                'of ${_steps.length}',
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                  color: AppColors.cream,
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
                backgroundColor: AppColors.chocolateDark,
                color: AppColors.warmIvory,
              ),
            ),
          ),
          const SizedBox(height: 32),

          // Step text
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: isCompleted
                  ? AppColors.withOpacity(AppColors.sage, 0.15)
                  : AppColors.chocolateDark,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: isCompleted ? AppColors.sage : AppColors.chocolateLight,
              ),
            ),
            child: Column(
              children: [
                // Completed checkmark
                if (isCompleted) ...[
                  const Icon(Icons.check_circle,
                      color: AppColors.sage, size: 32),
                  const SizedBox(height: 16),
                ],

                // Instruction text
                Text(
                  step,
                  style: TextStyle(
                    fontSize: 24,
                    height: 1.5,
                    color: isCompleted
                        ? AppColors.withOpacity(AppColors.warmIvory, 0.6)
                        : AppColors.warmIvory,
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
            _buildInlineTimer(timeMatch),
          ],

          // Swipe hint
          const SizedBox(height: 32),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.swipe, size: 16,
                  color: AppColors.withOpacity(AppColors.warmIvory, 0.4)),
              const SizedBox(width: 8),
              Text(
                'Swipe left/right to navigate',
                style: TextStyle(
                  fontSize: 12,
                  color: AppColors.withOpacity(AppColors.warmIvory, 0.4),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildInlineTimer(RegExpMatch match) {
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
        foregroundColor: AppColors.terracotta,
        side: const BorderSide(color: AppColors.terracotta),
      ),
    );
  }
}

class _ActiveTimer {
  final String label;
  final Duration duration;
  Duration remaining;
  final DateTime startTime;
  Timer? timer;

  _ActiveTimer({
    required this.label,
    required this.duration,
    required this.remaining,
    required this.startTime,
    this.timer,
  });
}
