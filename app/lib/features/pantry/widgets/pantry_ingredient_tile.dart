import 'package:flutter/material.dart';

import '../models/pantry_ingredient.dart';
import 'fuzzy_expiry_text.dart';

/// A single pantry row: ingredient name, quantity, fuzzy expiry, and a
/// color-coded leading bar that signals urgency at a glance.
class PantryIngredientTile extends StatelessWidget {
  final PantryIngredient item;
  final VoidCallback? onTap;
  /// Non-null only on rows in the "Expiring Soon" section — the pantry-7
  /// "Use me up" CTA routes to recipe search filtered by this ingredient.
  final VoidCallback? onUseMeUp;

  const PantryIngredientTile({
    super.key,
    required this.item,
    this.onTap,
    this.onUseMeUp,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final expiry = fuzzyExpiry(item.expiresAt);

    final q = item.quantityDisplay;
    final qStr = q == q.truncateToDouble() ? q.toInt().toString() : q.toString();
    final quantityLine =
        item.unitDisplay.isEmpty ? qStr : '$qStr ${item.unitDisplay}';

    return InkWell(
      onTap: onTap,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(width: 4, color: expiry.barColor),
          const SizedBox(width: 12),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 4),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.ingredientName ?? 'Unknown ingredient',
                    style: theme.textTheme.titleMedium,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    quantityLine,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    expiry.label,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: expiry.barColor,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  if (onUseMeUp != null) ...[
                    const SizedBox(height: 8),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: FilledButton.tonalIcon(
                        onPressed: onUseMeUp,
                        icon: const Icon(Icons.restaurant_menu, size: 18),
                        label: const Text('Use me up'),
                        style: FilledButton.styleFrom(
                          visualDensity: VisualDensity.compact,
                          padding: const EdgeInsets.symmetric(
                            horizontal: 12,
                            vertical: 4,
                          ),
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
          const Padding(
            padding: EdgeInsets.only(right: 12),
            child: Icon(Icons.chevron_right, size: 20),
          ),
        ],
      ),
    );
  }
}
