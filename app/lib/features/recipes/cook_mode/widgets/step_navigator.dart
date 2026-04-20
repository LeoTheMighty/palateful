import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../../core/theme/theme.dart';

class StepNavigator extends StatelessWidget {
  final int currentStep;
  final int totalSteps;
  final Set<int> completedSteps;
  final VoidCallback? onPrevious;
  final VoidCallback? onNext;
  final VoidCallback? onDone;
  final ValueChanged<int> onStepTap;
  final VoidCallback onLongPressStep;

  const StepNavigator({
    super.key,
    required this.currentStep,
    required this.totalSteps,
    required this.completedSteps,
    this.onPrevious,
    this.onNext,
    this.onDone,
    required this.onStepTap,
    required this.onLongPressStep,
  });

  @override
  Widget build(BuildContext context) {
    final isLastStep = currentStep == totalSteps - 1;
    final cook = context.cookModeTheme;
    final appColors = context.appColors;

    return SafeArea(
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: cook.cookSurface,
          boxShadow: [
            BoxShadow(
              color: cook.cookShadow,
              blurRadius: 8,
              offset: const Offset(0, -2),
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Prev/Next buttons
            Row(
              children: [
                // Previous
                Expanded(
                  child: _NavButton(
                    icon: Icons.arrow_back_rounded,
                    label: 'Prev',
                    onPressed: onPrevious,
                    alignment: MainAxisAlignment.start,
                  ),
                ),

                const SizedBox(width: 16),

                // Next/Done
                Expanded(
                  child: _NavButton(
                    icon: isLastStep
                        ? Icons.check_rounded
                        : Icons.arrow_forward_rounded,
                    label: isLastStep ? 'Done' : 'Next',
                    onPressed: isLastStep ? onDone : onNext,
                    alignment: MainAxisAlignment.end,
                    isPrimary: true,
                  ),
                ),
              ],
            ),

            const SizedBox(height: 16),

            // Step dots
            GestureDetector(
              onLongPress: onLongPressStep,
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: List.generate(totalSteps, (index) {
                    final isCurrent = index == currentStep;
                    // A pill only renders "completed" for non-current
                    // indices. The current pill never shows a check,
                    // regardless of set membership. See cmp-4 AC4.
                    final isCompleted =
                        !isCurrent && completedSteps.contains(index);

                    final semanticLabel = isCurrent
                        ? 'Step ${index + 1}, current'
                        : isCompleted
                            ? 'Step ${index + 1}, completed'
                            : 'Step ${index + 1}, upcoming';

                    return Semantics(
                      label: semanticLabel,
                      button: true,
                      container: true,
                      selected: isCurrent,
                      excludeSemantics: true,
                      child: GestureDetector(
                        onTap: () => onStepTap(index),
                        child: Container(
                          width: isCurrent ? 28 : 24,
                          height: 28,
                          margin: const EdgeInsets.symmetric(horizontal: 4),
                          decoration: BoxDecoration(
                            color: isCurrent
                                ? cook.cookAccent
                                : isCompleted
                                    ? cook.cookCompleted
                                    : cook.cookSurfaceDim,
                            borderRadius: BorderRadius.circular(14),
                            border: isCurrent
                                ? null
                                : Border.all(
                                    color: isCompleted
                                        ? cook.cookCompleted
                                        : cook.cookDivider,
                                  ),
                          ),
                          child: Center(
                            child: isCompleted
                                ? Icon(
                                    Icons.check,
                                    size: 14,
                                    color: cook.cookOnCompleted,
                                  )
                                : Text(
                                    '${index + 1}',
                                    style: TextStyle(
                                      fontSize: 12,
                                      fontWeight: FontWeight.w600,
                                      color: isCurrent
                                          ? cook.cookOnAccent
                                          : cook.cookOnSurface
                                              .withValues(alpha: 0.7),
                                    ),
                                  ),
                          ),
                        ),
                      ),
                    );
                  }),
                ),
              ),
            ),

            // Hint text
            const SizedBox(height: 8),
            Text(
              'Long press to mark all previous steps complete',
              style: TextStyle(
                fontSize: 11,
                color: appColors.textTertiary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _NavButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback? onPressed;
  final MainAxisAlignment alignment;
  final bool isPrimary;

  const _NavButton({
    required this.icon,
    required this.label,
    this.onPressed,
    required this.alignment,
    this.isPrimary = false,
  });

  @override
  Widget build(BuildContext context) {
    final isEnabled = onPressed != null;
    final cook = context.cookModeTheme;
    final appColors = context.appColors;

    return Material(
      color: isPrimary && isEnabled
          ? cook.cookAccent
          : isEnabled
              ? cook.cookSurfaceDim
              : cook.cookDivider,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: isEnabled
            ? () {
                HapticFeedback.selectionClick();
                onPressed!();
              }
            : null,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 22),
          child: Row(
            mainAxisAlignment: alignment,
            children: alignment == MainAxisAlignment.start
                ? [
                    Icon(
                      icon,
                      size: 20,
                      color: isEnabled
                          ? cook.cookOnSurface
                          : appColors.textDisabled,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      label,
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: isEnabled
                            ? cook.cookOnSurface
                            : appColors.textDisabled,
                      ),
                    ),
                  ]
                : [
                    Text(
                      label,
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: isPrimary && isEnabled
                            ? cook.cookOnAccent
                            : isEnabled
                                ? cook.cookOnSurface
                                : appColors.textDisabled,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Icon(
                      icon,
                      size: 20,
                      color: isPrimary && isEnabled
                          ? cook.cookOnAccent
                          : isEnabled
                              ? cook.cookOnSurface
                              : appColors.textDisabled,
                    ),
                  ],
          ),
        ),
      ),
    );
  }
}
