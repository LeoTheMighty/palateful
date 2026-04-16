import 'package:flutter/material.dart';

import '../../../shared/widgets/vibe_chip.dart';
import 'meal_filter_bar.dart';

/// Modal bottom sheet that groups meal-type and vibe filters in one place,
/// replacing the previous pair of horizontally-scrolling bars stacked on
/// the home screen.
///
/// Uses internal draft state so chip taps inside the sheet don't commit
/// to the parent screen until the user taps Apply. Drag-down dismiss acts
/// as cancel (the draft state is thrown away).
class FilterBottomSheet extends StatefulWidget {
  final MealFilter initialMeal;
  final String? initialVibe;
  final void Function(MealFilter meal, String? vibe) onApply;

  const FilterBottomSheet({
    super.key,
    required this.initialMeal,
    required this.initialVibe,
    required this.onApply,
  });

  static Future<void> show({
    required BuildContext context,
    required MealFilter initialMeal,
    required String? initialVibe,
    required void Function(MealFilter meal, String? vibe) onApply,
  }) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => FilterBottomSheet(
        initialMeal: initialMeal,
        initialVibe: initialVibe,
        onApply: onApply,
      ),
    );
  }

  @override
  State<FilterBottomSheet> createState() => _FilterBottomSheetState();
}

class _FilterBottomSheetState extends State<FilterBottomSheet> {
  late MealFilter _draftMeal;
  late String? _draftVibe;

  @override
  void initState() {
    super.initState();
    _draftMeal = widget.initialMeal;
    _draftVibe = widget.initialVibe;
  }

  void _clearAll() {
    setState(() {
      _draftMeal = MealFilter.all;
      _draftVibe = null;
    });
  }

  void _apply() {
    widget.onApply(_draftMeal, _draftVibe);
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Drag handle
            Center(
              child: Container(
                width: 36,
                height: 4,
                margin: const EdgeInsets.only(bottom: 12),
                decoration: BoxDecoration(
                  color: colorScheme.outlineVariant,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            Text(
              'Filters',
              style: textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 16),

            // Meals section
            Text(
              'Meals',
              style: textTheme.titleSmall?.copyWith(
                color: colorScheme.onSurfaceVariant,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 8),
            _MealChipWrap(
              selected: _draftMeal,
              onChanged: (m) => setState(() => _draftMeal = m),
            ),
            const SizedBox(height: 20),

            // Vibes section
            Text(
              'Vibes',
              style: textTheme.titleSmall?.copyWith(
                color: colorScheme.onSurfaceVariant,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 8),
            _VibeChipWrap(
              selected: _draftVibe,
              onChanged: (v) => setState(() => _draftVibe = v),
            ),
            const SizedBox(height: 24),

            // Action row
            Row(
              children: [
                TextButton(
                  onPressed: _clearAll,
                  child: const Text('Clear all'),
                ),
                const Spacer(),
                FilledButton(
                  onPressed: _apply,
                  child: const Text('Apply'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _MealChipWrap extends StatelessWidget {
  final MealFilter selected;
  final ValueChanged<MealFilter> onChanged;

  const _MealChipWrap({required this.selected, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    const entries = [
      (MealFilter.all, 'All', Icons.restaurant_menu),
      (MealFilter.breakfast, 'Breakfast', Icons.free_breakfast),
      (MealFilter.lunch, 'Lunch', Icons.lunch_dining),
      (MealFilter.dinner, 'Dinner', Icons.dinner_dining),
      (MealFilter.dessert, 'Dessert', Icons.cake),
      (MealFilter.snack, 'Snack', Icons.cookie),
    ];
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: entries.map((e) {
        final (filter, label, icon) = e;
        return _SheetFilterChip(
          icon: icon,
          label: label,
          isSelected: selected == filter,
          onTap: () => onChanged(filter),
        );
      }).toList(),
    );
  }
}

class _VibeChipWrap extends StatelessWidget {
  final String? selected;
  final ValueChanged<String?> onChanged;

  const _VibeChipWrap({required this.selected, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    final vibes = defaultVibeOptions.values.toList();
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        _SheetFilterChip(
          label: 'All',
          isSelected: selected == null,
          onTap: () => onChanged(null),
        ),
        ...vibes.map((v) => _SheetFilterChip(
              label: v.name,
              color: v.color,
              isSelected: selected == v.id,
              onTap: () => onChanged(v.id),
            )),
      ],
    );
  }
}

class _SheetFilterChip extends StatelessWidget {
  final IconData? icon;
  final String label;
  final Color? color;
  final bool isSelected;
  final VoidCallback onTap;

  const _SheetFilterChip({
    this.icon,
    required this.label,
    this.color,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final bg = isSelected
        ? (color ?? colorScheme.primary)
        : colorScheme.surfaceContainerHighest;
    final fg = isSelected
        ? (color != null ? Colors.white : colorScheme.onPrimary)
        : colorScheme.onSurface;

    return Material(
      color: bg,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (icon != null) ...[
                Icon(icon, size: 16, color: fg),
                const SizedBox(width: 6),
              ],
              Text(
                label,
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
    );
  }
}
