/// cmm-1 — `ActiveTimersRow` is the horizontally-scrolling chip row of
/// running timers, extracted out of `cook_mode_screen.dart` so meal
/// cook mode can reuse the exact rendering. Each timer is rendered as a
/// progress-ring chip with a remaining-time label and a close icon; tap
/// opens the timer detail sheet.
///
/// Display-only — countdown rebuilds come from the parent's per-second
/// `setState`, not an internal ticker. The parent owns timer state.

library;

import 'package:flutter/material.dart';

import '../../../../../core/theme/theme.dart';

/// One in-flight timer from the parent's perspective. Kept loose to
/// avoid coupling this widget to the private `_ActiveTimer` class in
/// `cook_mode_screen.dart`. `remaining` is non-final because the
/// parent mutates it on every per-second tick.
class ActiveTimerView {
  final String label;
  final Duration duration;
  Duration remaining;

  ActiveTimerView({
    required this.label,
    required this.duration,
    required this.remaining,
  });
}

class ActiveTimersRow<T extends ActiveTimerView> extends StatelessWidget {
  final List<T> timers;
  final void Function(T timer) onTap;
  final void Function(T timer) onCancel;

  /// cmmrf-6 — optional per-timer recipe-name builder. When non-null
  /// and returning a non-empty string, the chip prepends
  /// `{RecipeName} · ` to the countdown label. Null / empty falls
  /// back to the prefixless `MM:SS` copy (recipe-mode uses this
  /// unconditionally; meal-mode returns null for v1-restored timers
  /// whose `sourceRecipeId` is missing).
  final String? Function(T timer)? recipeNameForTimer;

  const ActiveTimersRow({
    super.key,
    required this.timers,
    required this.onTap,
    required this.onCancel,
    this.recipeNameForTimer,
  });

  @override
  Widget build(BuildContext context) {
    final cook = context.cookModeTheme;
    return Container(
      height: 44,
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: timers.length,
        separatorBuilder: (_, _) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final timer = timers[index];
          final totalSec = timer.duration.inSeconds;
          final progress = totalSec > 0
              ? 1 - (timer.remaining.inSeconds / totalSec)
              : 0.0;
          return GestureDetector(
            onTap: () => onTap(timer),
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
                  Flexible(
                    child: Text(
                      _labelFor(timer),
                      maxLines: 1,
                      softWrap: false,
                      overflow: TextOverflow.fade,
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: cook.cookTimer,
                        fontFeatures: const [FontFeature.tabularFigures()],
                      ),
                    ),
                  ),
                  const SizedBox(width: 4),
                  GestureDetector(
                    onTap: () => onCancel(timer),
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

  String _labelFor(T timer) {
    final countdown = _formatDuration(timer.remaining);
    final prefix = recipeNameForTimer?.call(timer);
    if (prefix == null || prefix.isEmpty) return countdown;
    return '$prefix · $countdown';
  }

  static String _formatDuration(Duration d) {
    final minutes = d.inMinutes;
    final seconds = d.inSeconds % 60;
    return '${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
  }
}
