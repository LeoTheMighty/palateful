import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';

/// Inline "See past X" gateway link rendered below an empty-state
/// illustration when lifetime history exists. Returns
/// `SizedBox.shrink()` when [count] is zero so the empty state stays
/// pure for brand-new users.
///
/// Visual language (afh-5 AC1):
/// - centred Text.rich with [label] + ` (N)` suffix
/// - underline + slightly-higher-contrast colour to signal "tappable"
/// - trailing `chevron_down` glyph to signal "expands inline" (not
///   navigates away)
/// - minimum 48dp tap target inside an InkWell
/// - Semantics label "Label, N items, tap to expand" for screen readers
class EmptyStateGatewayLink extends StatelessWidget {
  final int count;
  final String label;
  final VoidCallback onTap;

  const EmptyStateGatewayLink({
    super.key,
    required this.count,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    if (count == 0) return const SizedBox.shrink();

    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    // Gateway link is one step BRIGHTER than the muted "see-all-row"
    // token so it reads as interactive. Land between primary and the
    // muted token.
    final linkColor = AppColors.mutedOnSurface(colorScheme)
        .withValues(alpha: 0.85);

    return Semantics(
      label: '$label, $count items, tap to expand',
      button: true,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(12),
          child: Container(
            constraints: const BoxConstraints(minHeight: 48),
            alignment: Alignment.center,
            padding: const EdgeInsets.symmetric(
              horizontal: 16,
              vertical: 12,
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  '$label ($count)',
                  style: textTheme.bodyMedium?.copyWith(
                    color: linkColor,
                    decoration: TextDecoration.underline,
                    decorationColor: linkColor,
                  ),
                ),
                const SizedBox(width: 4),
                Icon(
                  Icons.keyboard_arrow_down,
                  size: 18,
                  color: linkColor,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
