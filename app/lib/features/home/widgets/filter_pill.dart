import 'package:flutter/material.dart';

/// Icon-only funnel button shown in the home header that opens the
/// combined filter + sort bottom sheet. A small dot badge appears when
/// any non-default sort or any filter is active — consolidating what
/// used to be a separate sort-chip row and filter pill into one affordance.
class FilterPill extends StatelessWidget {
  final bool isActive;
  final VoidCallback onTap;

  const FilterPill({
    super.key,
    required this.isActive,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Tooltip(
      message: 'Sort & filter',
      child: Material(
        color: colorScheme.surfaceContainerHighest,
        shape: const CircleBorder(),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          customBorder: const CircleBorder(),
          child: Padding(
            padding: const EdgeInsets.all(10),
            child: Stack(
              clipBehavior: Clip.none,
              children: [
                Icon(Icons.tune, size: 20, color: colorScheme.onSurface),
                if (isActive)
                  Positioned(
                    right: -2,
                    top: -2,
                    child: Container(
                      key: const ValueKey('filter_pill_active_dot'),
                      width: 8,
                      height: 8,
                      decoration: BoxDecoration(
                        color: colorScheme.primary,
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: colorScheme.surfaceContainerHighest,
                          width: 1.5,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
