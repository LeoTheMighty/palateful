import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../models/meal.dart';

/// One row of the Meal detail's component list. Shows thumbnail, name,
/// book-of-origin, prep/cook chips, and a trailing chevron (or nothing
/// in edit mode). Unavailable rows render muted.
class ComponentRow extends StatelessWidget {
  final MealComponent component;
  final VoidCallback? onTap;
  final Widget? trailing;

  const ComponentRow({
    super.key,
    required this.component,
    this.onTap,
    this.trailing,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final disabled = !component.available;

    return InkWell(
      onTap: disabled ? null : onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        child: Opacity(
          opacity: disabled ? 0.55 : 1.0,
          child: Row(
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(10),
                child: SizedBox(
                  width: 64,
                  height: 64,
                  child: component.imageUrl != null && component.available
                      ? CachedNetworkImage(
                          imageUrl: component.imageUrl!,
                          fit: BoxFit.cover,
                          errorWidget: (c, u, e) => _placeholder(colorScheme),
                        )
                      : _placeholder(colorScheme),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      component.displayName,
                      style: textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    if (disabled)
                      Padding(
                        padding: const EdgeInsets.only(top: 2),
                        child: Text(
                          'Unavailable',
                          style: textTheme.bodySmall?.copyWith(
                            color: colorScheme.error,
                          ),
                        ),
                      )
                    else ...[
                      if (component.bookName != null)
                        Text(
                          component.bookName!,
                          style: textTheme.bodySmall?.copyWith(
                            color: colorScheme.onSurfaceVariant,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      const SizedBox(height: 4),
                      Wrap(
                        spacing: 8,
                        runSpacing: 4,
                        children: [
                          if (component.prepTime != null)
                            _Chip(
                              icon: Icons.timer_outlined,
                              text: 'Prep ${component.prepTime}m',
                            ),
                          if (component.cookTime != null)
                            _Chip(
                              icon: Icons.local_fire_department_outlined,
                              text: 'Cook ${component.cookTime}m',
                            ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(width: 8),
              trailing ??
                  (disabled
                      ? const SizedBox.shrink()
                      : Icon(
                          Icons.chevron_right,
                          color: colorScheme.outline,
                        )),
            ],
          ),
        ),
      ),
    );
  }

  Widget _placeholder(ColorScheme colorScheme) => Container(
        color: colorScheme.surfaceContainerHighest,
        child: Icon(
          Icons.restaurant,
          size: 28,
          color: colorScheme.onSurfaceVariant,
        ),
      );
}

class _Chip extends StatelessWidget {
  final IconData icon;
  final String text;
  const _Chip({required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 12, color: colorScheme.outline),
        const SizedBox(width: 4),
        Text(
          text,
          style: textTheme.bodySmall?.copyWith(color: colorScheme.outline),
        ),
      ],
    );
  }
}
