import 'package:flutter/material.dart';

/// Horizontal scroller of category filter chips. OR-semantics:
/// selecting "produce" and "dairy" shows items from either category.
/// Empty selection = show everything.
class PantryFilterBar extends StatelessWidget {
  final List<String> availableCategories;
  final Set<String> selectedCategories;
  final ValueChanged<Set<String>> onChanged;

  const PantryFilterBar({
    super.key,
    required this.availableCategories,
    required this.selectedCategories,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    if (availableCategories.isEmpty) return const SizedBox.shrink();
    return SizedBox(
      height: 44,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12),
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
            child: FilterChip(
              label: const Text('All'),
              selected: selectedCategories.isEmpty,
              onSelected: (_) => onChanged(<String>{}),
            ),
          ),
          for (final c in availableCategories)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
              child: FilterChip(
                label: Text(c),
                selected: selectedCategories.contains(c),
                onSelected: (on) {
                  final next = Set<String>.from(selectedCategories);
                  if (on) {
                    next.add(c);
                  } else {
                    next.remove(c);
                  }
                  onChanged(next);
                },
              ),
            ),
        ],
      ),
    );
  }
}
