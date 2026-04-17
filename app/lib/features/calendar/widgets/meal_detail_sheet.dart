import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/di/injection.dart';
import '../models/meal_event.dart';
import '../services/meal_calendar_service.dart';
import 'recurrence_field.dart';

/// Bottom-sheet surfaced on calendar meal tap (bugs-cal-1). One primary
/// action (Open Recipe) plus a secondary icon row: Reschedule, Unschedule,
/// Mark as Cooked. The sheet is dismissed before any action fires so the
/// parent Navigator owns follow-up navigation.
///
/// Callbacks are void-returning so the caller handles its own async
/// (optimistic removal, snackbar-undo, etc.).
class MealDetailSheet extends StatefulWidget {
  final MealEvent event;

  /// Called when the user taps Reschedule after choosing a new datetime.
  /// The datetime is local-time; the caller is responsible for converting
  /// to UTC before writing.
  final Future<void> Function(DateTime newLocalDateTime) onReschedule;

  /// Called when the user taps Unschedule. Caller handles the undo
  /// snackbar (locked decision #3).
  final VoidCallback onUnschedule;

  /// Called when the user taps Mark as Cooked AND the recipe is attached.
  /// Null when no recipe — the action is disabled in that case.
  final VoidCallback? onMarkCooked;

  /// Called after a successful "End series today" so the caller can reload
  /// the calendar week.
  final VoidCallback? onSeriesEnded;

  const MealDetailSheet({
    super.key,
    required this.event,
    required this.onReschedule,
    required this.onUnschedule,
    required this.onMarkCooked,
    this.onSeriesEnded,
  });

  @override
  State<MealDetailSheet> createState() => _MealDetailSheetState();
}

class _MealDetailSheetState extends State<MealDetailSheet> {
  RecurrenceRule? _rule;
  bool _ruleLoadFailed = false;

  MealCalendarService get _service => getIt<MealCalendarService>();

  @override
  void initState() {
    super.initState();
    if (widget.event.recurrenceRuleId != null) {
      _loadRule();
    }
  }

  Future<void> _loadRule() async {
    try {
      final rule = await _service.getRecurrenceRule(
        widget.event.recurrenceRuleId!,
      );
      if (mounted) setState(() => _rule = rule);
    } catch (_) {
      if (mounted) setState(() => _ruleLoadFailed = true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final event = widget.event;
    final recipe = event.recipe;
    final isRecurring = event.recurrenceRuleId != null;

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

            // Header: thumbnail + title + scheduled local time
            Row(
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(10),
                    color: colorScheme.surfaceContainerHighest,
                  ),
                  clipBehavior: Clip.antiAlias,
                  child: recipe?.imageUrl != null
                      ? Image.network(
                          recipe!.imageUrl!,
                          fit: BoxFit.cover,
                          errorBuilder: (_, __, ___) => Icon(
                            Icons.restaurant,
                            color: colorScheme.secondary,
                          ),
                        )
                      : Icon(Icons.restaurant, color: colorScheme.secondary),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Flexible(
                            child: Text(
                              event.title,
                              style: textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.w600,
                              ),
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          if (isRecurring) ...[
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 6,
                                vertical: 2,
                              ),
                              decoration: BoxDecoration(
                                color: colorScheme.secondaryContainer,
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                'Recurring',
                                style: TextStyle(
                                  fontSize: 11,
                                  color: colorScheme.onSecondaryContainer,
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                      const SizedBox(height: 2),
                      Text(
                        _formatLocal(event.scheduledAt),
                        style: textTheme.bodySmall?.copyWith(
                          color: colorScheme.onSurfaceVariant,
                        ),
                      ),
                      if (isRecurring) ...[
                        const SizedBox(height: 4),
                        Text(
                          _ruleSummaryText(),
                          style: textTheme.bodySmall?.copyWith(
                            color: colorScheme.onSurfaceVariant,
                            fontStyle: FontStyle.italic,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),

            // Primary action: Open Recipe (full-width)
            FilledButton.icon(
              icon: const Icon(Icons.menu_book_outlined),
              label: const Text('Open Recipe'),
              onPressed: recipe == null
                  ? null
                  : () {
                      Navigator.pop(context);
                      context.push('/recipes/${recipe.id}');
                    },
              style: FilledButton.styleFrom(
                minimumSize: const Size.fromHeight(48),
              ),
            ),
            const SizedBox(height: 12),

            // Secondary icon row: Reschedule, Unschedule, Mark as Cooked
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                _SecondaryAction(
                  icon: Icons.event_repeat,
                  label: 'Reschedule',
                  onTap: () => _handleReschedule(context),
                ),
                _SecondaryAction(
                  icon: Icons.event_busy,
                  label: 'Unschedule',
                  destructive: true,
                  onTap: () {
                    Navigator.pop(context);
                    widget.onUnschedule();
                  },
                ),
                _SecondaryAction(
                  icon: Icons.restaurant_menu,
                  label: 'Mark Cooked',
                  onTap: widget.onMarkCooked == null
                      ? null
                      : () {
                          Navigator.pop(context);
                          widget.onMarkCooked!();
                        },
                  disabledReason: widget.onMarkCooked == null
                      ? 'No recipe attached'
                      : null,
                ),
              ],
            ),
            if (isRecurring && !_ruleLoadFailed) ...[
              const SizedBox(height: 12),
              Divider(color: colorScheme.outlineVariant),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: Icon(
                  Icons.stop_circle_outlined,
                  color: colorScheme.error,
                ),
                title: Text(
                  'End series today',
                  style: TextStyle(color: colorScheme.error),
                ),
                onTap: _handleEndSeries,
              ),
            ],
          ],
        ),
      ),
    );
  }

  Future<void> _handleEndSeries() async {
    final title = widget.event.title;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text('Stop repeating $title?'),
        content: const Text(
          'Future occurrences will be removed. Past occurrences stay.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Stop'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    try {
      await _service.deleteRecurrenceRule(widget.event.recurrenceRuleId!);
      if (!mounted) return;
      Navigator.pop(context);
      widget.onSeriesEnded?.call();
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Couldn't end series. Try again.")),
      );
    }
  }

  String _ruleSummaryText() {
    final rule = _rule;
    if (rule == null) {
      return _ruleLoadFailed ? 'Recurring meal' : 'Loading…';
    }
    final value = RecurrenceValue(
      interval: rule.interval,
      weekdays: rule.weekdays,
      monthlyNth: rule.monthlyNth,
      endDate: rule.endDate,
    );
    final summary = describeRecurrence(value);
    return '$summary · ${_mealTypeLabel(rule.mealType)}';
  }

  String _mealTypeLabel(String type) {
    switch (type) {
      case 'breakfast':
        return 'Breakfast';
      case 'lunch':
        return 'Lunch';
      case 'dinner':
        return 'Dinner';
      case 'snack':
        return 'Snack';
    }
    return type;
  }

  Future<void> _handleReschedule(BuildContext context) async {
    final now = DateTime.now();
    final current = widget.event.scheduledAt;

    // Pre-fill with the existing local time.
    final pickedDate = await showDatePicker(
      context: context,
      initialDate: current,
      firstDate: DateTime(now.year - 1),
      lastDate: DateTime(now.year + 2),
    );
    if (pickedDate == null || !context.mounted) return;

    final pickedTime = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(current),
    );
    if (pickedTime == null || !context.mounted) return;

    final local = DateTime(
      pickedDate.year,
      pickedDate.month,
      pickedDate.day,
      pickedTime.hour,
      pickedTime.minute,
    );

    if (!context.mounted) return;
    Navigator.pop(context);
    await widget.onReschedule(local);
  }

  String _formatLocal(DateTime dt) {
    final local = dt.toLocal();
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    ];
    final h12 = local.hour == 0
        ? 12
        : (local.hour > 12 ? local.hour - 12 : local.hour);
    final ampm = local.hour >= 12 ? 'PM' : 'AM';
    final mm = local.minute.toString().padLeft(2, '0');
    return '${months[local.month - 1]} ${local.day} · $h12:$mm $ampm';
  }
}

class _SecondaryAction extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback? onTap;
  final bool destructive;
  final String? disabledReason;

  const _SecondaryAction({
    required this.icon,
    required this.label,
    required this.onTap,
    this.destructive = false,
    this.disabledReason,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final enabled = onTap != null;
    final color = !enabled
        ? colorScheme.onSurface.withValues(alpha: 0.35)
        : (destructive ? colorScheme.error : colorScheme.primary);

    return Tooltip(
      message: disabledReason ?? '',
      preferBelow: true,
      waitDuration: const Duration(milliseconds: 500),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, color: color, size: 24),
              const SizedBox(height: 4),
              Text(
                label,
                style: TextStyle(
                  fontSize: 11,
                  color: color,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
