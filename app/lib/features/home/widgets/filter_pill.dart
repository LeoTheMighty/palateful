import 'package:flutter/material.dart';

/// Small tappable pill shown on the home screen that opens the filter
/// bottom sheet. Displays a count badge when any filters are active so
/// the user can tell at a glance whether the grid is filtered.
class FilterPill extends StatelessWidget {
  final int activeCount;
  final VoidCallback onTap;

  const FilterPill({
    super.key,
    required this.activeCount,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final hasActive = activeCount > 0;
    final bg = hasActive
        ? colorScheme.primary
        : colorScheme.surfaceContainerHighest;
    final fg = hasActive ? colorScheme.onPrimary : colorScheme.onSurface;
    final label = hasActive ? 'Filter ($activeCount)' : 'Filter';

    return Material(
      color: bg,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: 14,
            vertical: 8,
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.tune, size: 16, color: fg),
              const SizedBox(width: 6),
              Text(
                label,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                  color: fg,
                ),
              ),
              const SizedBox(width: 4),
              Icon(Icons.arrow_drop_down, size: 18, color: fg),
            ],
          ),
        ),
      ),
    );
  }
}
