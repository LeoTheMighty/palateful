/// cmmrf-3 — `RecipeToggleBar` renders a horizontally-scrollable row
/// of pills, one per component recipe in plan order, letting the user
/// swap the active recipe mid-cook. The meal cook screen mounts this
/// between the ingredient block and the step card; it is **hidden**
/// (renders nothing) for single-component meals.
///
/// Each pill carries the component's `{Name} {cur+1}/{total}` label;
/// active pills paint `cookAccent`, inactive pills are outlined,
/// complete pills get a trailing check (tappable to rewind), and
/// load-failed pills render disabled with a trailing ellipsis.
///
/// Pulse animation: when a timer fires on a non-active recipe, the
/// screen adds that recipe id to `pulsingRecipeIds` and the pill
/// performs a single `AnimatedScale` pulse (scale 1.08 over 300ms
/// with `Curves.easeOutBack`). The `onEnd` callback asks the parent
/// to clear the id.

library;

import 'package:flutter/material.dart';

import '../../../../../core/theme/theme.dart';
import '../../shared/cook_plan.dart';

class RecipeToggleBar extends StatelessWidget {
  final List<ComponentSummary> components;
  final String activeRecipeId;
  final Set<String> pulsingRecipeIds;
  final ValueChanged<String> onTap;

  /// Callback fired when a pulse-animation settles so the parent can
  /// remove the id from its `_pulsingRecipeIds` set. The id is passed
  /// back by the pill itself.
  final ValueChanged<String>? onPulseEnd;

  const RecipeToggleBar({
    super.key,
    required this.components,
    required this.activeRecipeId,
    required this.pulsingRecipeIds,
    required this.onTap,
    this.onPulseEnd,
  });

  @override
  Widget build(BuildContext context) {
    // Inherited-decision 6 — single-component meal renders nothing.
    if (components.length <= 1) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: IntrinsicHeight(
          child: Row(
            children: [
              for (var i = 0; i < components.length; i++) ...[
                if (i > 0) const SizedBox(width: 8),
                _Pill(
                  key: Key('toggle_pill_${components[i].recipeId}'),
                  summary: components[i],
                  isActive: components[i].recipeId == activeRecipeId,
                  isPulsing:
                      pulsingRecipeIds.contains(components[i].recipeId),
                  onTap: () {
                    if (components[i].loadFailed) return;
                    onTap(components[i].recipeId);
                  },
                  onPulseEnd: onPulseEnd,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _Pill extends StatelessWidget {
  final ComponentSummary summary;
  final bool isActive;
  final bool isPulsing;
  final VoidCallback onTap;
  final ValueChanged<String>? onPulseEnd;

  const _Pill({
    super.key,
    required this.summary,
    required this.isActive,
    required this.isPulsing,
    required this.onTap,
    this.onPulseEnd,
  });

  @override
  Widget build(BuildContext context) {
    final cook = context.cookModeTheme;
    final label = summary.loadFailed
        ? '${summary.name} …'
        : '${summary.name} ${summary.currentStep + 1}/${summary.totalSteps}';
    final textColor = summary.loadFailed
        ? cook.cookOnSurface.withValues(alpha: 0.4)
        : isActive
            ? cook.cookOnAccent
            : cook.cookOnSurface;
    final bgColor = isActive ? cook.cookAccent : Colors.transparent;
    final borderColor =
        isActive ? cook.cookAccent : cook.cookDivider;
    final pill = AnimatedScale(
      scale: isPulsing ? 1.08 : 1.0,
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeOutBack,
      onEnd: () {
        if (isPulsing) onPulseEnd?.call(summary.recipeId);
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        constraints: const BoxConstraints(
          minWidth: 72,
          maxWidth: 160,
          minHeight: 44,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: bgColor,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: borderColor),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Flexible(
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                  color: textColor,
                ),
              ),
            ),
            if (summary.isComplete && !summary.loadFailed) ...[
              const SizedBox(width: 4),
              Icon(
                Icons.check,
                size: 14,
                color: isActive ? cook.cookOnAccent : cook.cookCompleted,
              ),
            ],
          ],
        ),
      ),
    );
    if (summary.loadFailed) return pill;
    // Haptic lives inside `_setActiveRecipe` (parent) so same-recipe
    // taps don't fire it (cmmrf-3 spec).
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: pill,
    );
  }
}
