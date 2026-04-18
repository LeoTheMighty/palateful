import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/calendar.dart';
import '../providers/active_calendar_provider.dart';
import 'calendar_picker_sheet.dart';

/// Bottom sheet — "Calendars" header, picker list, "+ New Calendar" footer.
///
/// Tapping a row sets the active calendar and dismisses. Tapping a row's
/// chevron opens [onOpenSettings]. "+ New Calendar" delegates to
/// [onCreateCalendar]. cal-found-4 wires both to real sheets; this story
/// accepts the callbacks as stubs.
class CalendarSwitcherSheet extends ConsumerWidget {
  final VoidCallback? onCreateCalendar;
  final ValueChanged<Calendar>? onOpenSettings;

  const CalendarSwitcherSheet({
    super.key,
    this.onCreateCalendar,
    this.onOpenSettings,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final calendarsAsync = ref.watch(calendarsListProvider);
    final activeIdAsync = ref.watch(activeCalendarProvider);

    return SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 12),
            child: Text(
              'Calendars',
              style: theme.textTheme.titleLarge,
            ),
          ),
          calendarsAsync.when(
            data: (calendars) => CalendarPickerSheet(
              calendars: calendars,
              activeId: activeIdAsync.value,
              onSelect: (cal) async {
                await ref
                    .read(activeCalendarProvider.notifier)
                    .setActive(cal.id);
                if (context.mounted) Navigator.of(context).pop();
              },
              onOpenSettings: onOpenSettings,
            ),
            loading: () => const Padding(
              padding: EdgeInsets.all(24),
              child: Center(child: CircularProgressIndicator()),
            ),
            error: (err, _) => Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                children: [
                  Text(
                    'Calendars unavailable',
                    style: theme.textTheme.titleMedium,
                  ),
                  const SizedBox(height: 8),
                  TextButton(
                    onPressed: () => ref.invalidate(calendarsListProvider),
                    child: const Text('Retry'),
                  ),
                ],
              ),
            ),
          ),
          // "Shared with Me" section scaffolded but hidden until the
          // sharing epic. Must NOT render an empty shared section with
          // "nothing here yet" copy on day one.
          const Visibility(visible: false, child: SizedBox()),
          const Divider(height: 1),
          ListTile(
            leading: const Icon(Icons.add),
            title: const Text('New Calendar'),
            onTap: onCreateCalendar,
          ),
        ],
      ),
    );
  }
}
