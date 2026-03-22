import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/theme/theme.dart';
import '../models/shopping_list_item.dart';
import 'urgency_badge.dart';

/// Tile widget for displaying a shopping list item.
class ShoppingListItemTile extends StatelessWidget {
  final ShoppingListItem item;
  final VoidCallback? onTap;
  final VoidCallback? onLongPress;
  final ValueChanged<bool?>? onChecked;
  final bool showUrgency;
  final bool compact;

  const ShoppingListItemTile({
    super.key,
    required this.item,
    this.onTap,
    this.onLongPress,
    this.onChecked,
    this.showUrgency = true,
    this.compact = false,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap ?? () => _toggleChecked(context),
        onLongPress: onLongPress,
        borderRadius: BorderRadius.circular(8),
        child: Container(
          padding: EdgeInsets.symmetric(
            horizontal: compact ? 8 : 12,
            vertical: compact ? 6 : 10,
          ),
          child: Row(
            children: [
              _buildCheckbox(context),
              SizedBox(width: compact ? 8 : 12),
              Expanded(child: _buildContent(context)),
              if (showUrgency && item.urgencyLevel != UrgencyLevel.none)
                Padding(
                  padding: const EdgeInsets.only(left: 8),
                  child: UrgencyBadge(
                    urgency: item.urgencyLevel,
                    compact: compact,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildCheckbox(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final appColors = context.appColors;
    return GestureDetector(
      onTap: () => _toggleChecked(context),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        width: compact ? 20 : 24,
        height: compact ? 20 : 24,
        decoration: BoxDecoration(
          color: item.isChecked ? appColors.success : Colors.transparent,
          border: Border.all(
            color: item.isChecked ? appColors.success : colorScheme.outline,
            width: 2,
          ),
          borderRadius: BorderRadius.circular(6),
        ),
        child: item.isChecked
            ? Icon(
                Icons.check,
                size: compact ? 14 : 16,
                color: colorScheme.surface,
              )
            : null,
      ),
    );
  }

  void _toggleChecked(BuildContext context) {
    HapticFeedback.lightImpact();
    onChecked?.call(!item.isChecked);
  }

  Widget _buildContent(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final appColors = context.appColors;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                item.name,
                style: TextStyle(
                  fontSize: compact ? 14 : 15,
                  fontWeight: FontWeight.w500,
                  color: item.isChecked
                      ? appColors.textDisabled
                      : colorScheme.onSurface,
                  decoration:
                      item.isChecked ? TextDecoration.lineThrough : null,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            if (item.quantityDisplay.isNotEmpty) ...[
              const SizedBox(width: 8),
              Text(
                item.quantityDisplay,
                style: TextStyle(
                  fontSize: compact ? 12 : 13,
                  color: item.isChecked
                      ? appColors.textDisabled
                      : colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ],
        ),
        if (!compact && _hasSubtext) ...[
          const SizedBox(height: 2),
          _buildSubtext(appColors),
        ],
      ],
    );
  }

  bool get _hasSubtext =>
      item.category != null ||
      item.notes != null ||
      item.addedByUserName != null;

  Widget _buildSubtext(PalatefulColors appColors) {
    final parts = <String>[];

    if (item.category != null) {
      parts.add(item.category!);
    }
    if (item.notes != null && item.notes!.isNotEmpty) {
      parts.add(item.notes!);
    }
    if (item.addedByUserName != null) {
      parts.add('by ${item.addedByUserName}');
    }

    return Text(
      parts.join(' • '),
      style: TextStyle(
        fontSize: 12,
        color: item.isChecked
            ? appColors.textDisabled
            : appColors.textTertiary,
      ),
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
    );
  }
}

/// Section header for grouped items.
class ShoppingListSection extends StatelessWidget {
  final String title;
  final int itemCount;
  final Widget? trailing;

  const ShoppingListSection({
    super.key,
    required this.title,
    required this.itemCount,
    this.trailing,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 16, 12, 8),
      child: Row(
        children: [
          Text(
            title,
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: colorScheme.onSurfaceVariant,
              letterSpacing: 0.5,
            ),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: colorScheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(
              itemCount.toString(),
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: colorScheme.onSurfaceVariant,
              ),
            ),
          ),
          const Spacer(),
          if (trailing != null) trailing!,
        ],
      ),
    );
  }
}
