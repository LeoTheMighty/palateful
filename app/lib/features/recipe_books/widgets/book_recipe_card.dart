import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../../../shared/widgets/mixed_card_body.dart';
import '../../../shared/widgets/mixed_card_metrics.dart';

/// Recipe card used by the book-detail mixed grid. Extracted from
/// `recipe_book_detail_screen.dart` (rbv101) so its geometry can be
/// pinned by a widget test alongside `MealTile`.
///
/// Geometry lives in [MixedCardBody]: the card fills the box the grid
/// hands it and falls back to a fixed height when unbounded, so it comes
/// out the same size as the meal tiles it is interleaved with no matter
/// how much metadata the recipe carries.
class BookRecipeCard extends StatelessWidget {
  final dynamic recipe;
  final VoidCallback onTap;
  final VoidCallback? onLongPress;
  final bool isSelectMode;
  final bool isSelected;

  const BookRecipeCard({
    super.key,
    required this.recipe,
    required this.onTap,
    this.onLongPress,
    this.isSelectMode = false,
    this.isSelected = false,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final imageUrl = recipe['image_url'] as String?;
    final tags = (recipe['tags'] as List?)?.cast<String>() ?? [];

    return Card(
      margin: const EdgeInsets.only(bottom: kMixedCardBottomMargin),
      clipBehavior: Clip.antiAlias,
      shape: isSelected
          ? RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: BorderSide(color: colorScheme.primary, width: 2),
            )
          : null,
      child: InkWell(
        onTap: onTap,
        onLongPress: onLongPress,
        child: Stack(
          children: [
            MixedCardBody(
              hero: imageUrl != null
                  ? CachedNetworkImage(
                      imageUrl: imageUrl,
                      fit: BoxFit.cover,
                      placeholder: (context, url) => Container(
                        color: colorScheme.surfaceContainerHighest,
                        child: const Center(
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                      ),
                      errorWidget: (context, url, error) => Container(
                        color: colorScheme.surfaceContainerHighest,
                        child: Icon(
                          Icons.restaurant,
                          size: 48,
                          color: colorScheme.onSurfaceVariant,
                        ),
                      ),
                    )
                  : Container(
                      color: colorScheme.surfaceContainerHighest,
                      child: Icon(
                        Icons.restaurant,
                        size: 48,
                        color: colorScheme.onSurfaceVariant,
                      ),
                    ),
              info: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      recipe['name'] ?? 'Untitled',
                      style: textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 6),

                    // Metadata chips
                    Wrap(
                      spacing: 8,
                      runSpacing: 4,
                      children: [
                        if (recipe['prep_time'] != null)
                          _MetadataChip(
                            icon: Icons.timer_outlined,
                            label: 'Prep ${recipe['prep_time']}m',
                          ),
                        if (recipe['cook_time'] != null)
                          _MetadataChip(
                            icon: Icons.local_fire_department_outlined,
                            label: 'Cook ${recipe['cook_time']}m',
                          ),
                        if (recipe['servings'] != null)
                          _MetadataChip(
                            icon: Icons.people_outline,
                            label: 'Serves ${recipe['servings']}',
                          ),
                      ],
                    ),

                    // Tags — capped at two (matching home's `RecipeCard`)
                    // so the row can't push past the info block.
                    if (tags.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 6,
                        runSpacing: 4,
                        children: tags
                            .take(2)
                            .map((tag) => Chip(
                                  label: Text(tag),
                                  labelStyle: textTheme.labelSmall,
                                  materialTapTargetSize:
                                      MaterialTapTargetSize.shrinkWrap,
                                  visualDensity: VisualDensity.compact,
                                  backgroundColor:
                                      colorScheme.surfaceContainerHighest,
                                  padding: EdgeInsets.zero,
                                ))
                            .toList(),
                      ),
                    ],
                  ],
                ),
              ),
            ),
            // Selection checkbox overlay
            if (isSelectMode)
              Positioned(
                top: 8,
                right: 8,
                child: Container(
                  decoration: BoxDecoration(
                    color: isSelected
                        ? colorScheme.primary
                        : colorScheme.surface.withValues(alpha: 0.8),
                    shape: BoxShape.circle,
                    border: Border.all(
                      color:
                          isSelected ? colorScheme.primary : colorScheme.outline,
                      width: 2,
                    ),
                  ),
                  padding: const EdgeInsets.all(2),
                  child: Icon(
                    isSelected ? Icons.check : null,
                    size: 18,
                    color:
                        isSelected ? colorScheme.onPrimary : Colors.transparent,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _MetadataChip extends StatelessWidget {
  final IconData icon;
  final String label;

  const _MetadataChip({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: colorScheme.outline),
        const SizedBox(width: 4),
        Text(
          label,
          style: textTheme.bodySmall?.copyWith(
            color: colorScheme.outline,
          ),
        ),
      ],
    );
  }
}
