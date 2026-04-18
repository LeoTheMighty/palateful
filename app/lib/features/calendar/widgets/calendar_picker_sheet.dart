import 'package:flutter/material.dart';

import '../models/calendar.dart';

/// Reusable calendar list. Consumed by:
///   - [CalendarSwitcherSheet] — row tap sets active calendar + dismisses.
///   - cal-found-5's plan-meal Calendar row picker — row tap sets form state.
///
/// Row body and trailing chevron are distinct hit targets: tapping the body
/// fires [onSelect]; tapping the chevron fires [onOpenSettings] (when
/// supplied). Principle #4 of the calendars epic.
class CalendarPickerSheet extends StatelessWidget {
  final List<Calendar> calendars;
  final String? activeId;
  final ValueChanged<Calendar> onSelect;
  final ValueChanged<Calendar>? onOpenSettings;

  const CalendarPickerSheet({
    super.key,
    required this.calendars,
    required this.activeId,
    required this.onSelect,
    this.onOpenSettings,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final cal in calendars)
          _CalendarPickerRow(
            calendar: cal,
            isActive: cal.id == activeId,
            onSelect: () => onSelect(cal),
            onOpenSettings:
                onOpenSettings == null ? null : () => onOpenSettings!(cal),
            theme: theme,
          ),
      ],
    );
  }
}

class _CalendarPickerRow extends StatelessWidget {
  final Calendar calendar;
  final bool isActive;
  final VoidCallback onSelect;
  final VoidCallback? onOpenSettings;
  final ThemeData theme;

  const _CalendarPickerRow({
    required this.calendar,
    required this.isActive,
    required this.onSelect,
    required this.theme,
    this.onOpenSettings,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = theme.colorScheme;
    return Row(
      children: [
        Expanded(
          child: InkWell(
            key: Key('calendar-picker-row-body-${calendar.id}'),
            onTap: onSelect,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
              child: Row(
                children: [
                  Icon(
                    isActive ? Icons.check_circle : Icons.circle_outlined,
                    size: 20,
                    color: isActive
                        ? colorScheme.primary
                        : colorScheme.outlineVariant,
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          calendar.name,
                          style: theme.textTheme.titleMedium,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 2),
                        Text(
                          calendar.isOwner ? 'Owned by you' : 'Shared with you',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
        if (onOpenSettings != null)
          SizedBox(
            width: 56,
            child: IconButton(
              key: Key('calendar-picker-row-settings-${calendar.id}'),
              icon: const Icon(Icons.chevron_right),
              tooltip: 'Calendar settings',
              color: colorScheme.onSurfaceVariant,
              onPressed: onOpenSettings,
            ),
          ),
      ],
    );
  }
}
