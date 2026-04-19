import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../meals/models/meal.dart';

/// "Which recipe?" bottom sheet (mcal-8).
///
/// Shown from `MealDetailSheet` → Open Recipe when the event is linked
/// to a Meal with 2+ available components. Lists available component
/// recipes; tapping a row pops the sheet and pushes `/recipes/:id`.
/// Unavailable components are **omitted entirely** so the user isn't
/// offered a dead link (epic Principle 9).
class CalendarRecipeChooserSheet extends StatelessWidget {
  final List<MealComponent> components;
  final String mealName;

  const CalendarRecipeChooserSheet({
    super.key,
    required this.components,
    required this.mealName,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final available = components.where((c) => c.available).toList()
      ..sort((a, b) => a.orderIndex.compareTo(b.orderIndex));

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
            Text(
              'Which recipe?',
              style: textTheme.titleMedium
                  ?.copyWith(fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 4),
            Text(
              mealName,
              style: textTheme.bodySmall
                  ?.copyWith(color: colorScheme.onSurfaceVariant),
            ),
            const SizedBox(height: 12),
            if (available.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 24),
                child: Text(
                  'No recipes are available to open.',
                  style: textTheme.bodyMedium
                      ?.copyWith(color: colorScheme.onSurfaceVariant),
                  textAlign: TextAlign.center,
                ),
              )
            else
              ...available.map((c) => _ComponentRow(
                    component: c,
                    onTap: () {
                      Navigator.of(context).pop();
                      context.push('/recipes/${c.recipeId}');
                    },
                  )),
          ],
        ),
      ),
    );
  }
}

class _ComponentRow extends StatelessWidget {
  final MealComponent component;
  final VoidCallback onTap;

  const _ComponentRow({required this.component, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 10),
        child: Row(
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(8),
                color: colorScheme.surfaceContainerHighest,
              ),
              clipBehavior: Clip.antiAlias,
              child: component.imageUrl != null
                  ? Image.network(
                      component.imageUrl!,
                      fit: BoxFit.cover,
                      errorBuilder: (_, _, _) => Icon(
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
                  Text(
                    component.name,
                    style: textTheme.bodyMedium
                        ?.copyWith(fontWeight: FontWeight.w500),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if ((component.bookName ?? '').isNotEmpty)
                    Text(
                      component.bookName!,
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
}
