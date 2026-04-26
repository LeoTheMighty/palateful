import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Story 5: filter chip rendered above the recipe list (home + book
/// detail) that toggles the "hide recipes attached to a meal" filter.
///
/// Copy when [active] (filter ON, recipes-in-meals are hidden):
///   `"N recipes · M hidden in meals"`
/// Copy when filter is OFF:
///   `"N recipes · M shown in meals"`
///
/// The chip is a no-op (and visually muted) when [hidden] == 0 — the
/// user has no recipes attached to any meal, so the filter has nothing
/// to do. Tapping it still flips state for symmetry, but the copy
/// drops the trailing clause.
class HideInMealsChip extends StatelessWidget {
  /// Number of recipes currently visible in the list (post-filter).
  final int visibleCount;

  /// Number of recipes that are attached to at least one meal — the
  /// pool the filter operates on. Equals zero when no recipe is in
  /// any meal yet.
  final int hiddenCount;

  /// True when the filter is currently hiding meal-attached recipes.
  final bool active;

  /// Tap handler — toggles `active` upstream.
  final VoidCallback onTap;

  const HideInMealsChip({
    super.key,
    required this.visibleCount,
    required this.hiddenCount,
    required this.active,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final visibleNoun =
        visibleCount == 1 ? 'recipe' : 'recipes';

    String trailing = '';
    if (hiddenCount > 0) {
      trailing = active
          ? ' · $hiddenCount hidden in meals'
          : ' · $hiddenCount shown in meals';
    }
    final copy = '$visibleCount $visibleNoun$trailing';

    final bg = active
        ? colorScheme.primaryContainer
        : colorScheme.surfaceContainerHighest;
    final fg = active
        ? colorScheme.onPrimaryContainer
        : colorScheme.onSurface;

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
      child: Align(
        alignment: Alignment.centerLeft,
        child: Material(
          color: bg,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            key: const ValueKey('hide_in_meals_chip'),
            onTap: () {
              HapticFeedback.selectionClick();
              onTap();
            },
            child: Padding(
              padding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    active
                        ? Icons.visibility_off_outlined
                        : Icons.visibility_outlined,
                    size: 16,
                    color: fg,
                  ),
                  const SizedBox(width: 6),
                  Text(
                    copy,
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w500,
                      color: fg,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Story 5: empty state shown when the hide-in-meals filter is on
/// AND every recipe in this surface is attached to a meal. Frames it
/// as a celebration ("nothing left to organize") with a one-tap
/// affordance to disable the filter.
class HideInMealsEmptyState extends StatelessWidget {
  final VoidCallback onShowAll;

  const HideInMealsEmptyState({super.key, required this.onShowAll});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.celebration_outlined,
              size: 64,
              color: colorScheme.primary,
            ),
            const SizedBox(height: 16),
            Text(
              'Everything is in a Meal',
              style: textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              'Loose recipes are tidied up. Tap to show them anyway.',
              style: textTheme.bodyMedium?.copyWith(
                color: colorScheme.onSurfaceVariant,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              key: const ValueKey('hide_in_meals_show_all'),
              onPressed: onShowAll,
              icon: const Icon(Icons.visibility_outlined),
              label: const Text('Show all recipes'),
            ),
          ],
        ),
      ),
    );
  }
}
