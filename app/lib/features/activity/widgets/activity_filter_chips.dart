import 'package:flutter/material.dart';

/// Canonical filter enum for the Activity Hub. Deep-link schema:
/// `/activity?filter=<enum>`. Future epics that add categories must extend
/// this enum rather than invent a new query param (locked decision).
enum ActivityFilter { all, imports, partner, reminders }

extension ActivityFilterX on ActivityFilter {
  String get label {
    switch (this) {
      case ActivityFilter.all:
        return 'All';
      case ActivityFilter.imports:
        return 'Imports';
      case ActivityFilter.partner:
        return 'Partner';
      case ActivityFilter.reminders:
        return 'Reminders';
    }
  }

  String get wire {
    switch (this) {
      case ActivityFilter.all:
        return 'all';
      case ActivityFilter.imports:
        return 'imports';
      case ActivityFilter.partner:
        return 'partner';
      case ActivityFilter.reminders:
        return 'reminders';
    }
  }

  static ActivityFilter fromWire(String? wire) {
    switch (wire) {
      case 'imports':
        return ActivityFilter.imports;
      case 'partner':
        return ActivityFilter.partner;
      case 'reminders':
        return ActivityFilter.reminders;
      case 'all':
      default:
        return ActivityFilter.all;
    }
  }
}

/// Horizontal chip row rendered at the top of the Activity Hub. Only chips
/// that have matching content are shown, except for `all`, which is always
/// visible. Imports chip is always visible too when live-progress activity
/// has been surfaced (the caller decides via [availableFilters]).
class ActivityFilterChips extends StatelessWidget {
  final ActivityFilter selected;
  final Set<ActivityFilter> availableFilters;
  final ValueChanged<ActivityFilter> onSelected;

  const ActivityFilterChips({
    super.key,
    required this.selected,
    required this.availableFilters,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    final effective = {
      ActivityFilter.all,
      ...availableFilters,
    };
    if (effective.length == 1) {
      // Only `all` is available — don't render a single-chip row.
      return const SizedBox.shrink();
    }

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: ActivityFilter.values
            .where(effective.contains)
            .map((filter) {
              return Padding(
                padding: const EdgeInsets.only(right: 8),
                child: ChoiceChip(
                  label: Text(filter.label),
                  selected: selected == filter,
                  onSelected: (_) => onSelected(filter),
                ),
              );
            })
            .toList(),
      ),
    );
  }
}
