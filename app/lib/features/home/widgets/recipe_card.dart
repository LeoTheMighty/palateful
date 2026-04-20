import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../core/theme/theme.dart';
import '../../../shared/widgets/vibe_chip.dart';

class RecipeCard extends StatelessWidget {
  final dynamic recipe;
  final VoidCallback onTap;
  final VoidCallback? onLongPress;
  final VoidCallback? onFavoriteToggle;

  /// When true the card renders a selection checkmark + dim overlay.
  /// Wired by home's selection mode (hmp-2).
  final bool selected;

  const RecipeCard({
    super.key,
    required this.recipe,
    required this.onTap,
    this.onLongPress,
    this.onFavoriteToggle,
    this.selected = false,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final appColors = context.appColors;

    final imageUrl = recipe['image_url'];
    final name = recipe['name'] ?? 'Untitled';
    final prepTime = recipe['prep_time'];
    final cookTime = recipe['cook_time'];
    final totalTime = (prepTime ?? 0) + (cookTime ?? 0);
    final timesCooked = recipe['times_cooked'] ?? 0;
    final tags = recipe['tags'] as List<dynamic>? ?? [];
    final ingredients = recipe['ingredients'] as List<dynamic>? ?? [];
    final mealType = recipe['meal_type'];
    final isFavorite = recipe['is_favorite'] == true;
    final primaryVibe = recipe['primary_vibe'] as String?;
    final secondaryVibe = recipe['secondary_vibe'] as String?;

    return Card(
      clipBehavior: Clip.antiAlias,
      shape: selected
          ? RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: BorderSide(color: colorScheme.primary, width: 2),
            )
          : null,
      child: InkWell(
        onTap: () {
          HapticFeedback.selectionClick();
          onTap();
        },
        onLongPress: onLongPress != null
            ? () {
                HapticFeedback.mediumImpact();
                onLongPress!();
              }
            : null,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Image with favorite overlay
            Stack(
              children: [
                AspectRatio(
                  aspectRatio: 1.2,
                  child: imageUrl != null
                      ? CachedNetworkImage(
                          imageUrl: imageUrl,
                          fit: BoxFit.cover,
                          placeholder: (context, url) => const Center(child: CircularProgressIndicator(strokeWidth: 2)),
                          errorWidget: (context, url, error) => _buildPlaceholder(colorScheme),
                        )
                      : _buildPlaceholder(colorScheme),
                ),
                if (onFavoriteToggle != null)
                  Positioned(
                    top: 4,
                    right: 4,
                    child: GestureDetector(
                      onTap: () {
                        HapticFeedback.selectionClick();
                        onFavoriteToggle!();
                      },
                      child: Container(
                        padding: const EdgeInsets.all(6),
                        decoration: BoxDecoration(
                          color: const Color(0x4D000000),
                          shape: BoxShape.circle,
                        ),
                        child: Icon(
                          isFavorite ? Icons.favorite : Icons.favorite_border,
                          size: 18,
                          color: isFavorite ? AppColors.favorite : colorScheme.surface,
                        ),
                      ),
                    ),
                  ),
                if (selected)
                  Positioned.fill(
                    child: IgnorePointer(
                      child: Container(
                        color: colorScheme.primary.withValues(alpha: 0.35),
                        alignment: Alignment.center,
                        child: Container(
                          padding: const EdgeInsets.all(6),
                          decoration: BoxDecoration(
                            color: colorScheme.primary,
                            shape: BoxShape.circle,
                          ),
                          child: Icon(
                            Icons.check_circle,
                            color: colorScheme.onPrimary,
                            size: 32,
                          ),
                        ),
                      ),
                    ),
                  ),
              ],
            ),

            // Content
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Meal type badge (if set)
                    if (mealType != null) ...[
                      _MealBadge(mealType: mealType),
                      const SizedBox(height: 4),
                    ],

                    // Name
                    Text(
                      name,
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: colorScheme.onSurface,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),

                    const SizedBox(height: 6),

                    // Vibes
                    if (primaryVibe != null) ...[
                      VibeChips(
                        primaryVibe: primaryVibe,
                        secondaryVibe: secondaryVibe,
                      ),
                      const SizedBox(height: 6),
                    ],

                    // Tags
                    if (tags.isNotEmpty) ...[
                      Wrap(
                        spacing: 4,
                        runSpacing: 4,
                        children: tags
                            .take(2)
                            .map((tag) => _TagChip(tag: tag.toString()))
                            .toList(),
                      ),
                      const SizedBox(height: 6),
                    ],

                    // Ingredient preview
                    if (ingredients.isNotEmpty)
                      Text(
                        _formatIngredientPreview(ingredients),
                        style: TextStyle(
                          fontSize: 12,
                          color: appColors.textTertiary,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),

                    const Spacer(),

                    // Bottom row: time + times cooked
                    Row(
                      children: [
                        if (totalTime > 0) ...[
                          Icon(Icons.schedule,
                              size: 14, color: appColors.textTertiary),
                          const SizedBox(width: 4),
                          Text(
                            '${totalTime}m',
                            style: TextStyle(
                              fontSize: 12,
                              color: appColors.textTertiary,
                            ),
                          ),
                        ],
                        const Spacer(),
                        if (timesCooked > 0) ...[
                          Icon(Icons.restaurant,
                              size: 14, color: colorScheme.secondary),
                          const SizedBox(width: 4),
                          Text(
                            'x$timesCooked',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w500,
                              color: colorScheme.secondary,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPlaceholder(ColorScheme colorScheme) {
    return Container(
      color: colorScheme.surfaceContainerHighest,
      child: Center(
        child: Icon(
          Icons.restaurant,
          size: 40,
          color: colorScheme.secondary,
        ),
      ),
    );
  }

  String _formatIngredientPreview(List<dynamic> ingredients) {
    final names = ingredients
        .take(3)
        .map((i) => i['ingredient']?['canonical_name'] ?? '')
        .where((n) => n.isNotEmpty)
        .toList();

    if (names.isEmpty) return '';
    if (names.length <= 2) return names.join(', ');
    return '${names.take(2).join(', ')}...';
  }
}

class _MealBadge extends StatelessWidget {
  final String mealType;

  const _MealBadge({required this.mealType});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final appColors = context.appColors;

    final (icon, color) = switch (mealType.toLowerCase()) {
      'breakfast' => ('🌅', colorScheme.tertiary),
      'lunch' => ('☀️', colorScheme.secondary),
      'dinner' => ('🌙', colorScheme.primary),
      'dessert' => ('🍰', colorScheme.error),
      'snack' => ('🍿', appColors.success),
      _ => ('🍽️', appColors.textTertiary),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        icon,
        style: const TextStyle(fontSize: 10),
      ),
    );
  }
}

class _TagChip extends StatelessWidget {
  final String tag;

  const _TagChip({required this.tag});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        tag,
        style: TextStyle(
          fontSize: 10,
          color: colorScheme.onSurfaceVariant,
        ),
      ),
    );
  }
}
