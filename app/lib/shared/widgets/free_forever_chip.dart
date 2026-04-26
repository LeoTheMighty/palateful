import 'package:flutter/material.dart';

/// pos-6b: canonical "Unlimited — free forever" affordance for any
/// limit-shaped surface. Renders where a competitor app would show a
/// paywall (import button, household-add sheet, recipe-count footer,
/// etc.) and tells the user the same surface is free, unlimited, here.
///
/// **Cross-epic contract:** every future epic that touches a surface
/// where competitors paywall must mount this widget rather than
/// invent its own affordance copy. Specifically named by the locked
/// decisions in `epic-recime-positioning` ("Locked decisions to
/// propagate to later epics" §2). No feature-specific copy
/// permitted — keeps the message consistent across surfaces.
///
/// Three flavors of the same shape:
/// - `FreeForeverChip()` — default `Unlimited — free forever`.
/// - `FreeForeverChip.import()` — same chip with import-shaped
///   subtitle (`No 5/week cap. No premium tier.`).
/// - `FreeForeverChip.household()` — household-add-shaped subtitle
///   (`No seat limits. Invite anyone.`).
///
/// Variants are constants — adding a fourth requires touching this
/// file (so the cross-epic contract stays auditable). No runtime-
/// configurable copy.
class FreeForeverChip extends StatelessWidget {
  const FreeForeverChip({
    super.key,
    this.subtitle,
  });

  /// Variant for limit-shaped surfaces in the recipe-import flow.
  /// (e.g. AddRecipeSheet footer, future Recime-mass-import.)
  const FreeForeverChip.import({super.key})
      : subtitle = 'No 5/week cap. No premium tier.';

  /// Variant for limit-shaped surfaces in the household-share flow.
  /// (e.g. recipe-book invite sheet, calendar share sheet.)
  const FreeForeverChip.household({super.key})
      : subtitle = 'No seat limits. Invite anyone.';

  /// Optional secondary line. When null the chip renders just the
  /// canonical `Unlimited — free forever` headline.
  final String? subtitle;

  static const String headline = 'Unlimited — free forever';

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    return Semantics(
      container: true,
      label: subtitle == null ? headline : '$headline. $subtitle',
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: colorScheme.primaryContainer.withValues(alpha: 0.4),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: colorScheme.primary.withValues(alpha: 0.18),
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.all_inclusive,
              size: 18,
              color: colorScheme.primary,
            ),
            const SizedBox(width: 10),
            Flexible(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    headline,
                    style: textTheme.labelLarge?.copyWith(
                      fontWeight: FontWeight.w600,
                      color: colorScheme.onSurface,
                    ),
                  ),
                  if (subtitle != null) ...[
                    const SizedBox(height: 2),
                    Text(
                      subtitle!,
                      style: textTheme.bodySmall?.copyWith(
                        color: colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
