import 'package:flutter/material.dart';

import '../../../shared/widgets/vibe_chip.dart';
import 'meal_filter_bar.dart';

/// Sort options for the home recipe grid. Moved here from the deleted
/// sort_chips widget so the combined sort+filter sheet is the single
/// source of truth.
enum SortOption { best, newest, popular, quickest, lastCooked, random }

/// hmp-4: "Show" axis — filters the grid by tile kind. Radio-style;
/// only one value at a time. Default `all` keeps pre-epic behavior.
enum ShowTypeFilter { all, recipesOnly, mealsOnly }

/// Snapshot of the sheet's applied state, used for snackbar-undo of the
/// Clear-all action. Home screen captures pre-clear state and restores
/// it if the user taps Undo within the snackbar window.
class HomeFilterState {
  final MealFilter meal;
  final String? vibe;
  final SortOption sort;
  final ShowTypeFilter showType;
  final bool hideComponentsOfMeals;

  const HomeFilterState({
    required this.meal,
    required this.vibe,
    required this.sort,
    this.showType = ShowTypeFilter.all,
    this.hideComponentsOfMeals = true,
  });

  static const defaults = HomeFilterState(
    meal: MealFilter.all,
    vibe: null,
    sort: SortOption.best,
    showType: ShowTypeFilter.all,
    hideComponentsOfMeals: true,
  );

  bool get isDefault =>
      meal == defaults.meal &&
      vibe == defaults.vibe &&
      sort == defaults.sort &&
      showType == defaults.showType &&
      hideComponentsOfMeals == defaults.hideComponentsOfMeals;
}

/// Combined bottom sheet for Sort + Filters. Sort is monoexclusive
/// (radio list); filters (meal, vibe) are multiselect chip groups.
/// Both commit together on Apply; drag-down dismiss acts as cancel.
class FilterBottomSheet extends StatefulWidget {
  final HomeFilterState initialState;
  final void Function(HomeFilterState state) onApply;

  const FilterBottomSheet({
    super.key,
    required this.initialState,
    required this.onApply,
  });

  static Future<void> show({
    required BuildContext context,
    required HomeFilterState initialState,
    required void Function(HomeFilterState state) onApply,
  }) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => FilterBottomSheet(
        initialState: initialState,
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
  late SortOption _draftSort;
  late ShowTypeFilter _draftShowType;
  late bool _draftHideComponents;

  @override
  void initState() {
    super.initState();
    _draftMeal = widget.initialState.meal;
    _draftVibe = widget.initialState.vibe;
    _draftSort = widget.initialState.sort;
    _draftShowType = widget.initialState.showType;
    _draftHideComponents = widget.initialState.hideComponentsOfMeals;
  }

  void _clearAll() {
    setState(() {
      _draftMeal = HomeFilterState.defaults.meal;
      _draftVibe = HomeFilterState.defaults.vibe;
      _draftSort = HomeFilterState.defaults.sort;
      _draftShowType = HomeFilterState.defaults.showType;
      _draftHideComponents = HomeFilterState.defaults.hideComponentsOfMeals;
    });
  }

  void _apply() {
    widget.onApply(HomeFilterState(
      meal: _draftMeal,
      vibe: _draftVibe,
      sort: _draftSort,
      showType: _draftShowType,
      hideComponentsOfMeals: _draftHideComponents,
    ));
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return SafeArea(
      child: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
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
                'Sort & filter',
                style: textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 16),

              Text(
                'Sort by',
                style: textTheme.titleSmall?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 8),
              _SortRadioList(
                selected: _draftSort,
                onChanged: (s) => setState(() => _draftSort = s),
              ),
              const SizedBox(height: 20),

              Text(
                'Show',
                style: textTheme.titleSmall?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 8),
              _ShowTypeChipWrap(
                selected: _draftShowType,
                onChanged: (s) => setState(() => _draftShowType = s),
              ),
              const SizedBox(height: 20),

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
      ),
    );
  }
}

class _SortRadioList extends StatelessWidget {
  final SortOption selected;
  final ValueChanged<SortOption> onChanged;

  const _SortRadioList({
    required this.selected,
    required this.onChanged,
  });

  static const _entries = [
    (SortOption.best, Icons.star_rounded, 'Best'),
    (SortOption.newest, Icons.fiber_new_rounded, 'Newest'),
    (SortOption.popular, Icons.local_fire_department_rounded, 'Popular'),
    (SortOption.quickest, Icons.schedule_rounded, 'Quickest'),
    (SortOption.lastCooked, Icons.restaurant_rounded, 'Last cooked'),
    (SortOption.random, Icons.shuffle_rounded, 'Random'),
  ];

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Column(
      children: _entries.map((entry) {
        final (option, icon, label) = entry;
        final isSelected = selected == option;
        return InkWell(
          onTap: () => onChanged(option),
          borderRadius: BorderRadius.circular(8),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 4),
            child: Row(
              children: [
                Icon(
                  icon,
                  size: 20,
                  color: isSelected
                      ? colorScheme.primary
                      : colorScheme.onSurfaceVariant,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    label,
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                      color: isSelected
                          ? colorScheme.primary
                          : colorScheme.onSurface,
                    ),
                  ),
                ),
                Icon(
                  isSelected
                      ? Icons.radio_button_checked
                      : Icons.radio_button_unchecked,
                  size: 20,
                  color: isSelected
                      ? colorScheme.primary
                      : colorScheme.onSurfaceVariant,
                ),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }
}

class _ShowTypeChipWrap extends StatelessWidget {
  final ShowTypeFilter selected;
  final ValueChanged<ShowTypeFilter> onChanged;

  const _ShowTypeChipWrap({required this.selected, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    const entries = [
      (ShowTypeFilter.all, 'All', Icons.all_inclusive),
      (ShowTypeFilter.recipesOnly, 'Recipes only', Icons.restaurant_menu),
      (ShowTypeFilter.mealsOnly, 'Meals only', Icons.layers_outlined),
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
