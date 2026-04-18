import 'package:flutter/material.dart';

import '../models/meal.dart';
import 'component_collage_hero.dart';

/// Meal grid tile. Fork of `_RecipeCard` (not an extension) — see the
/// epic's Frontend Changes § Decision: RecipeCard.
///
/// Hero: `ComponentCollageHero` with the meal's (up to 4)
/// thumbnails + `+N` overlay when the meal has more than 4 components.
/// Body: meal name, optional description, and a decorative "N recipes"
/// badge (non-tappable — whole-tile tap opens `/meals/:id`).
class MealTile extends StatelessWidget {
  final MealSummary meal;
  final VoidCallback onTap;
  final VoidCallback? onLongPress;

  const MealTile({
    super.key,
    required this.meal,
    required this.onTap,
    this.onLongPress,
  });

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final colorScheme = Theme.of(context).colorScheme;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        onLongPress: onLongPress,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              height: 180,
              width: double.infinity,
              child: ComponentCollageHero(
                components: _buildComponentsFromSummary(meal),
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    meal.name,
                    style: textTheme.titleMedium
                        ?.copyWith(fontWeight: FontWeight.w600),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if ((meal.description ?? '').isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Text(
                      meal.description!,
                      style: textTheme.bodySmall?.copyWith(
                        color: colorScheme.onSurfaceVariant,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                  const SizedBox(height: 8),
                  Align(
                    alignment: Alignment.centerRight,
                    child: _RecipeCountBadge(count: meal.componentCount),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Builds a lightweight `MealComponent` list from a summary so we can
/// reuse `ComponentCollageHero` without introducing a second layout.
/// The collage uses only `imageUrl` + `available` + the list length,
/// so the stub fields are fine.
List<MealComponent> _buildComponentsFromSummary(MealSummary s) {
  final urls = s.componentImageUrls;
  return List.generate(s.componentCount, (i) {
    final url = i < urls.length ? urls[i] : null;
    return MealComponent(
      recipeId: 'stub-$i',
      name: '',
      orderIndex: i,
      imageUrl: url,
    );
  });
}

class _RecipeCountBadge extends StatelessWidget {
  final int count;
  const _RecipeCountBadge({required this.count});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: colorScheme.secondaryContainer,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        '$count recipes',
        style: textTheme.labelSmall?.copyWith(
          color: colorScheme.onSecondaryContainer,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
