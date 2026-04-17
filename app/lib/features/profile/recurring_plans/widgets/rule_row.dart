import 'package:flutter/material.dart';

import '../../../calendar/models/meal_event.dart';
import '../../../calendar/widgets/recurrence_field.dart';

/// Single row on the Recurring Plans list. Shows meal-type icon (or recipe
/// thumbnail when available), the rule title, a summary line, and an
/// active/ended chip. Muted when the rule has ended.
class RuleRow extends StatelessWidget {
  final RecurrenceRule rule;
  final VoidCallback onTap;
  final bool isEnded;

  const RuleRow({
    super.key,
    required this.rule,
    required this.onTap,
    this.isEnded = false,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    final title = rule.title ??
        (rule.recipeId != null ? 'Recipe meal' : 'Recurring meal');
    final summary = describeRecurrence(RecurrenceValue(
      interval: rule.interval,
      weekdays: rule.weekdays,
      monthlyNth: rule.monthlyNth,
      endDate: rule.endDate,
    ));

    final contentColor =
        isEnded ? colorScheme.onSurface.withValues(alpha: 0.5) : null;

    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(8),
                color: colorScheme.surfaceContainerHighest,
              ),
              alignment: Alignment.center,
              child: Icon(
                Icons.repeat,
                color: colorScheme.primary.withValues(
                  alpha: isEnded ? 0.4 : 1.0,
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                      color: contentColor,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '$summary · ${_mealTypeLabel(rule.mealType)}',
                    style: textTheme.bodySmall?.copyWith(
                      color: contentColor ?? colorScheme.onSurfaceVariant,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            _chip(colorScheme),
          ],
        ),
      ),
    );
  }

  Widget _chip(ColorScheme colorScheme) {
    final label = isEnded ? 'Ended' : 'Active';
    final bg = isEnded
        ? colorScheme.surfaceContainerHighest
        : colorScheme.secondaryContainer;
    final fg = isEnded
        ? colorScheme.onSurface.withValues(alpha: 0.6)
        : colorScheme.onSecondaryContainer;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          color: fg,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
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
}
