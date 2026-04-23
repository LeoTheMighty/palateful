import 'package:flutter/material.dart';

import '../../../../../core/theme/theme.dart';

/// Shows a Cupertino-style bottom-sheet overlay when a cook-mode timer
/// expires with the app in foreground on the cook-mode route. Renders the
/// same four actions as the iOS notification category (`TIMER_ADD_2_MIN`,
/// `TIMER_ADD_5_MIN`, `TIMER_RESET`, `TIMER_DISMISS`) as big 2×2
/// tap-targets. Each tap closes the sheet and fires the caller-supplied
/// callback; the expired timer is already removed from `_activeTimers`
/// by the caller, so drag-down dismiss is also safe.
///
/// Returns when the sheet is dismissed (either via an action tap or a
/// drag-down).
Future<void> showTimerCompletionOverlay({
  required BuildContext context,
  required String label,
  String? recipeName,
  int? stepNumber,
  required VoidCallback onAdd2,
  required VoidCallback onAdd5,
  required VoidCallback onReset,
  required VoidCallback onStop,
}) {
  final cook = context.cookModeTheme;
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: cook.cookSurface,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (sheetContext) => _TimerCompletionOverlay(
      label: label,
      recipeName: recipeName,
      stepNumber: stepNumber,
      onAdd2: onAdd2,
      onAdd5: onAdd5,
      onReset: onReset,
      onStop: onStop,
    ),
  );
}

class _TimerCompletionOverlay extends StatelessWidget {
  const _TimerCompletionOverlay({
    required this.label,
    required this.recipeName,
    required this.stepNumber,
    required this.onAdd2,
    required this.onAdd5,
    required this.onReset,
    required this.onStop,
  });

  final String label;
  final String? recipeName;
  final int? stepNumber;
  final VoidCallback onAdd2;
  final VoidCallback onAdd5;
  final VoidCallback onReset;
  final VoidCallback onStop;

  @override
  Widget build(BuildContext context) {
    final cook = context.cookModeTheme;
    final screenHeight = MediaQuery.of(context).size.height;
    final targetHeight = (screenHeight * 0.4).clamp(280.0, 420.0);
    final showSubtitle = recipeName != null && recipeName!.isNotEmpty;
    final subtitle = showSubtitle
        ? (stepNumber != null
            ? '$recipeName · Step ${stepNumber! + 1}'
            : recipeName!)
        : null;

    return SafeArea(
      child: Container(
        constraints: BoxConstraints(minHeight: targetHeight),
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Center(
              child: Container(
                width: 36,
                height: 4,
                decoration: BoxDecoration(
                  color: cook.cookOnSurface.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 16),
            const Center(
              child: Text(
                '⏱️',
                style: TextStyle(fontSize: 40),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              "Time's up — $label",
              key: const Key('timer_overlay_title'),
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w600,
                color: cook.cookOnSurface,
              ),
            ),
            if (subtitle != null) ...[
              const SizedBox(height: 4),
              Text(
                subtitle,
                key: const Key('timer_overlay_subtitle'),
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 14,
                  color: cook.cookOnSurface.withValues(alpha: 0.7),
                ),
              ),
            ],
            const SizedBox(height: 20),
            Row(
              children: [
                Expanded(
                  child: _ActionButton(
                    key: const Key('timer_overlay_add_2'),
                    label: '+ 2 min',
                    background: cook.cookAccent,
                    foreground: cook.cookOnAccent,
                    onTap: () {
                      Navigator.of(context).pop();
                      onAdd2();
                    },
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _ActionButton(
                    key: const Key('timer_overlay_add_5'),
                    label: '+ 5 min',
                    background: cook.cookAccent,
                    foreground: cook.cookOnAccent,
                    onTap: () {
                      Navigator.of(context).pop();
                      onAdd5();
                    },
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: _ActionButton(
                    key: const Key('timer_overlay_reset'),
                    label: 'Reset',
                    background: cook.cookSurfaceDim,
                    foreground: cook.cookOnSurface,
                    onTap: () {
                      Navigator.of(context).pop();
                      onReset();
                    },
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _ActionButton(
                    key: const Key('timer_overlay_stop'),
                    label: 'Stop',
                    background: const Color(0xFFB33A3A),
                    foreground: Colors.white,
                    onTap: () {
                      Navigator.of(context).pop();
                      onStop();
                    },
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _ActionButton extends StatelessWidget {
  const _ActionButton({
    super.key,
    required this.label,
    required this.background,
    required this.foreground,
    required this.onTap,
  });

  final String label;
  final Color background;
  final Color foreground;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return FilledButton(
      onPressed: onTap,
      style: FilledButton.styleFrom(
        backgroundColor: background,
        foregroundColor: foreground,
        minimumSize: const Size.fromHeight(56),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),
      child: Text(
        label,
        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
      ),
    );
  }
}
