import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../../core/theme/app_colors.dart';

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

    return SafeArea(
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.warmWhite,
          boxShadow: [
            BoxShadow(
              color: AppColors.shadow,
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
                    final isCompleted = completedSteps.contains(index);

                    return GestureDetector(
                      onTap: () => onStepTap(index),
                      child: Container(
                        width: isCurrent ? 28 : 24,
                        height: 28,
                        margin: const EdgeInsets.symmetric(horizontal: 4),
                        decoration: BoxDecoration(
                          color: isCurrent
                              ? AppColors.chocolate
                              : isCompleted
                                  ? AppColors.sage
                                  : AppColors.beige,
                          borderRadius: BorderRadius.circular(14),
                          border: isCurrent
                              ? null
                              : Border.all(
                                  color: isCompleted
                                      ? AppColors.sage
                                      : AppColors.beigeAccent,
                                ),
                        ),
                        child: Center(
                          child: isCompleted && !isCurrent
                              ? const Icon(
                                  Icons.check,
                                  size: 14,
                                  color: AppColors.cream,
                                )
                              : Text(
                                  '${index + 1}',
                                  style: TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w600,
                                    color: isCurrent
                                        ? AppColors.cream
                                        : AppColors.textSecondary,
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
            const Text(
              'Long press to mark all previous steps complete',
              style: TextStyle(
                fontSize: 11,
                color: AppColors.textTertiary,
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

    return Material(
      color: isPrimary && isEnabled
          ? AppColors.chocolate
          : isEnabled
              ? AppColors.beige
              : AppColors.divider,
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
                          ? AppColors.textPrimary
                          : AppColors.textDisabled,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      label,
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: isEnabled
                            ? AppColors.textPrimary
                            : AppColors.textDisabled,
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
                            ? AppColors.cream
                            : isEnabled
                                ? AppColors.textPrimary
                                : AppColors.textDisabled,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Icon(
                      icon,
                      size: 20,
                      color: isPrimary && isEnabled
                          ? AppColors.cream
                          : isEnabled
                              ? AppColors.textPrimary
                              : AppColors.textDisabled,
                    ),
                  ],
          ),
        ),
      ),
    );
  }
}
