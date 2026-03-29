import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'vibe_chip.dart';

/// Horizontal scrolling vibe filter bar. Same pattern as MealFilterBar.
class VibeFilterBar extends StatelessWidget {
  final String? selected;
  final ValueChanged<String?> onChanged;

  const VibeFilterBar({
    super.key,
    required this.selected,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final vibes = defaultVibeOptions.values.toList();

    return SizedBox(
      height: 40,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        children: [
          // "All" chip
          _VibeFilterChip(
            label: 'All',
            color: colorScheme.primary,
            isSelected: selected == null,
            onTap: () {
              HapticFeedback.selectionClick();
              onChanged(null);
            },
          ),
          // One chip per vibe
          ...vibes.map((vibe) => _VibeFilterChip(
                label: vibe.name,
                color: vibe.color,
                isSelected: selected == vibe.id,
                onTap: () {
                  HapticFeedback.selectionClick();
                  onChanged(vibe.id);
                },
              )),
        ],
      ),
    );
  }
}

class _VibeFilterChip extends StatelessWidget {
  final String label;
  final Color color;
  final bool isSelected;
  final VoidCallback onTap;

  const _VibeFilterChip({
    required this.label,
    required this.color,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: Material(
        color: isSelected ? color : colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(20),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(20),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            child: Text(
              label,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w500,
                color: isSelected ? Colors.white : colorScheme.onSurface,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
