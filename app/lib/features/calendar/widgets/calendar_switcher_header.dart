import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/calendar.dart';
import '../providers/active_calendar_provider.dart';
import 'calendar_switcher_sheet.dart';

/// Header chip/pill shown at the top of [CalendarScreen].
///
/// Shows the active calendar's name + chevron-down. Tappable across its
/// full width; tap opens [CalendarSwitcherSheet]. Callbacks for
/// create/settings are forwarded to the sheet — cal-found-4 supplies
/// real handlers; in this story, they may be left null.
class CalendarSwitcherHeader extends ConsumerWidget {
  final VoidCallback? onCreateCalendar;
  final ValueChanged<Calendar>? onOpenSettings;

  const CalendarSwitcherHeader({
    super.key,
    this.onCreateCalendar,
    this.onOpenSettings,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final activeCalAsync = ref.watch(activeCalendarProviderObject);
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    final label = activeCalAsync.when(
      data: (cal) => cal?.name ?? 'Calendar',
      loading: () => 'Calendar',
      error: (_, _) => 'Calendars unavailable',
    );

    return InkWell(
      onTap: () => _openSwitcher(context),
      borderRadius: BorderRadius.circular(20),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Flexible(
              child: Text(
                label,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: colorScheme.onSurface,
                ),
              ),
            ),
            const SizedBox(width: 4),
            Icon(
              Icons.arrow_drop_down,
              color: colorScheme.onSurfaceVariant,
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _openSwitcher(BuildContext context) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => CalendarSwitcherSheet(
        onCreateCalendar: onCreateCalendar == null
            ? null
            : () {
                Navigator.of(context).pop();
                onCreateCalendar!();
              },
        onOpenSettings: onOpenSettings == null
            ? null
            : (cal) {
                Navigator.of(context).pop();
                onOpenSettings!(cal);
              },
      ),
    );
  }
}
