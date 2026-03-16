import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../core/theme/app_colors.dart';

class RecipeCard extends StatelessWidget {
  final dynamic recipe;
  final VoidCallback onTap;
  final VoidCallback? onLongPress;
  final VoidCallback? onFavoriteToggle;

  const RecipeCard({
    super.key,
    required this.recipe,
    required this.onTap,
    this.onLongPress,
    this.onFavoriteToggle,
  });

  @override
  Widget build(BuildContext context) {
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

    return Card(
      clipBehavior: Clip.antiAlias,
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
                      ? Image.network(
                          imageUrl,
                          fit: BoxFit.cover,
                          errorBuilder: (_, __, ___) => _buildPlaceholder(),
                        )
                      : _buildPlaceholder(),
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
                          color: Colors.black.withValues(alpha: 0.3),
                          shape: BoxShape.circle,
                        ),
                        child: Icon(
                          isFavorite ? Icons.favorite : Icons.favorite_border,
                          size: 18,
                          color: isFavorite ? Colors.red : Colors.white,
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
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: AppColors.textPrimary,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),

                    const SizedBox(height: 6),

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
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppColors.textTertiary,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),

                    const Spacer(),

                    // Bottom row: time + times cooked
                    Row(
                      children: [
                        if (totalTime > 0) ...[
                          const Icon(Icons.schedule,
                              size: 14, color: AppColors.textTertiary),
                          const SizedBox(width: 4),
                          Text(
                            '${totalTime}m',
                            style: const TextStyle(
                              fontSize: 12,
                              color: AppColors.textTertiary,
                            ),
                          ),
                        ],
                        const Spacer(),
                        if (timesCooked > 0) ...[
                          const Icon(Icons.restaurant,
                              size: 14, color: AppColors.hazelnut),
                          const SizedBox(width: 4),
                          Text(
                            'x$timesCooked',
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w500,
                              color: AppColors.hazelnut,
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

  Widget _buildPlaceholder() {
    return Container(
      color: AppColors.beige,
      child: const Center(
        child: Icon(
          Icons.restaurant,
          size: 40,
          color: AppColors.hazelnut,
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
    final (icon, color) = switch (mealType.toLowerCase()) {
      'breakfast' => ('🌅', AppColors.terracotta),
      'lunch' => ('☀️', AppColors.hazelnut),
      'dinner' => ('🌙', AppColors.chocolate),
      'dessert' => ('🍰', AppColors.coral),
      'snack' => ('🍿', AppColors.sage),
      _ => ('🍽️', AppColors.textTertiary),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: AppColors.withOpacity(color, 0.15),
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
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: AppColors.beige,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        tag,
        style: const TextStyle(
          fontSize: 10,
          color: AppColors.textSecondary,
        ),
      ),
    );
  }
}
