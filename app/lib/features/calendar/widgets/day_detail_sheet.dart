import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../meals/widgets/meal_tile.dart' show kMealComponentCountLabel;
import '../models/meal_event.dart';
import '../providers/meal_events_provider.dart';

/// Bottom-sheet surfaced on calendar empty-day tap (bugs-cal-1). Renders
/// every meal for the day as an inline-expandable row and, when the day is
/// empty, an inline CTA to plan a meal. The sheet never stacks on another
/// sheet: tapping a meal row dismisses this sheet and the caller opens the
/// meal detail sheet (locked decision #14 — no sheet-on-sheet).
///
/// rmc-3: events come from `mealEventsByDayProvider((date, calendarId))`
/// — no callback back to the parent for refresh. The provider
/// subscribes to the MutationBus and re-fetches on any event that
/// lands on this day.
class DayDetailSheet extends ConsumerWidget {
  final DateTime day;
  final String? calendarId;

  /// Fired when the user taps a meal row. Caller pops this sheet before
  /// opening the meal detail sheet.
  final ValueChanged<MealEvent> onMealTap;

  /// Fired when the user taps "Plan a meal" from an empty-day state or the
  /// header action button.
  final VoidCallback onPlanMeal;

  const DayDetailSheet({
    super.key,
    required this.day,
    required this.onMealTap,
    required this.onPlanMeal,
    this.calendarId,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final normalized = DateTime(day.year, day.month, day.day);
    final asyncEvents = ref.watch(mealEventsByDayProvider(
      MealEventsDayKey(date: normalized, calendarId: calendarId),
    ));
    // Use the last-known data during refetch so the sheet doesn't flash
    // to a spinner after a mutation.
    final events = asyncEvents.value ?? const <MealEvent>[];

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: colorScheme.outlineVariant,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 16),

            Row(
              children: [
                Expanded(
                  child: Text(
                    _formatDay(day),
                    style: textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.add),
                  tooltip: 'Plan a meal',
                  onPressed: () {
                    Navigator.pop(context);
                    onPlanMeal();
                  },
                ),
              ],
            ),
            const SizedBox(height: 4),

            if (events.isEmpty)
              _EmptyDayRow(onPlanMeal: () {
                Navigator.pop(context);
                onPlanMeal();
              })
            else
              ...events.map((event) => _DayMealRow(
                    event: event,
                    onTap: () {
                      Navigator.pop(context);
                      onMealTap(event);
                    },
                  )),
          ],
        ),
      ),
    );
  }

  String _formatDay(DateTime dt) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final target = DateTime(dt.year, dt.month, dt.day);
    if (target == today) return 'Today';
    if (target == today.add(const Duration(days: 1))) return 'Tomorrow';
    if (target == today.subtract(const Duration(days: 1))) return 'Yesterday';
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    ];
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    final dayName = days[target.weekday - 1];
    return '$dayName · ${months[target.month - 1]} ${target.day}';
  }
}

class _EmptyDayRow extends StatelessWidget {
  final VoidCallback onPlanMeal;

  const _EmptyDayRow({required this.onPlanMeal});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 24),
      child: Center(
        child: TextButton.icon(
          icon: const Icon(Icons.add),
          label: const Text('Plan a meal'),
          onPressed: onPlanMeal,
          style: TextButton.styleFrom(
            foregroundColor: colorScheme.primary,
          ),
        ),
      ),
    );
  }
}

class _DayMealRow extends StatelessWidget {
  final MealEvent event;
  final VoidCallback onTap;

  const _DayMealRow({required this.event, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final recipe = event.recipe;
    final isMealEvent = event.mealId != null;
    final mealThumbUrl =
        (event.mealSummary?.componentImageUrls.isNotEmpty ?? false)
            ? event.mealSummary!.componentImageUrls.first
            : null;

    return InkWell(
      borderRadius: BorderRadius.circular(12),
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 10),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(8),
                color: colorScheme.surfaceContainerHighest,
              ),
              clipBehavior: Clip.antiAlias,
              child: isMealEvent
                  ? (mealThumbUrl != null
                      ? CachedNetworkImage(
                          imageUrl: mealThumbUrl,
                          fit: BoxFit.cover,
                          errorWidget: (_, _, _) => Icon(
                            Icons.layers,
                            color: colorScheme.secondary,
                          ),
                        )
                      : Icon(Icons.layers, color: colorScheme.secondary))
                  : (recipe?.imageUrl != null
                      ? CachedNetworkImage(
                          imageUrl: recipe!.imageUrl!,
                          fit: BoxFit.cover,
                          errorWidget: (_, _, _) => Icon(
                            Icons.restaurant,
                            color: colorScheme.secondary,
                          ),
                        )
                      : Icon(Icons.restaurant, color: colorScheme.secondary)),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      if (isMealEvent) ...[
                        Icon(
                          Icons.layers,
                          size: 12,
                          color: colorScheme.onSurface.withValues(alpha: 0.6),
                        ),
                        const SizedBox(width: 4),
                      ],
                      Flexible(
                        child: Text(
                          event.title,
                          style: textTheme.bodyMedium?.copyWith(
                            fontWeight: FontWeight.w500,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(
                    isMealEvent && event.mealSummary != null
                        ? '${event.mealType.displayName} · '
                            '${_time(event.scheduledAt)} · '
                            '${kMealComponentCountLabel(event.mealSummary!.componentCount)}'
                        : '${event.mealType.displayName} · ${_time(event.scheduledAt)}',
                    style: textTheme.bodySmall?.copyWith(
                      color: colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            Icon(Icons.chevron_right, color: colorScheme.outline),
          ],
        ),
      ),
    );
  }

  String _time(DateTime dt) {
    final local = dt.toLocal();
    final h12 = local.hour == 0
        ? 12
        : (local.hour > 12 ? local.hour - 12 : local.hour);
    final ampm = local.hour >= 12 ? 'PM' : 'AM';
    final mm = local.minute.toString().padLeft(2, '0');
    return '$h12:$mm $ampm';
  }
}
