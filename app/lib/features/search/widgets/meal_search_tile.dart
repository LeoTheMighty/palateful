// md-5: Search-results tile for a Meal.
//
// Horizontal ListTile-style row (not a grid card — that's the home
// grid's MealTile). Shows:
//   * 100×100 collage of up to 4 component images (same visual concept
//     as `ComponentCollageHero` but simplified to a 2×2 grid for the
//     search-row constraint).
//   * Meal name + optional book-context line.
//   * Decorative "N recipes" badge.
//   * If `matchedComponent != null` — a muted "Matches: <component>"
//     subtitle so the user understands why the Meal surfaced on a
//     component-name hit.

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

class MealSearchTile extends StatelessWidget {
  final String mealId;
  final String name;
  final String? bookName;
  final int componentCount;
  final List<String> componentImageUrls;
  final String? matchedComponentName;
  final VoidCallback onTap;

  const MealSearchTile({
    super.key,
    required this.mealId,
    required this.name,
    required this.componentCount,
    required this.componentImageUrls,
    required this.onTap,
    this.bookName,
    this.matchedComponentName,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    String context1 = bookName ?? '';
    if (context1.isNotEmpty) {
      context1 = '$context1 · $componentCount recipes';
    } else {
      context1 = '$componentCount recipes';
    }
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: Card(
        clipBehavior: Clip.antiAlias,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        child: InkWell(
          onTap: onTap,
          child: SizedBox(
            height: 100,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                SizedBox(
                  width: 100,
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      _Collage(urls: componentImageUrls),
                      Positioned(
                        right: 4,
                        bottom: 4,
                        child: _RecipeCountBadge(count: componentCount),
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 8),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          name,
                          style: textTheme.titleSmall
                              ?.copyWith(fontWeight: FontWeight.w600),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 2),
                        Text(
                          context1,
                          style: textTheme.bodySmall
                              ?.copyWith(color: colorScheme.onSurfaceVariant),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        if (matchedComponentName != null) ...[
                          const SizedBox(height: 2),
                          Text(
                            'Matches: $matchedComponentName',
                            style: textTheme.bodySmall?.copyWith(
                              color: colorScheme.onSurfaceVariant,
                              fontStyle: FontStyle.italic,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Collage extends StatelessWidget {
  final List<String> urls;
  const _Collage({required this.urls});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    if (urls.isEmpty) {
      return Container(
        color: colorScheme.surfaceContainerHighest,
        child: Icon(
          Icons.set_meal_outlined,
          color: colorScheme.onSurfaceVariant,
        ),
      );
    }
    if (urls.length == 1) {
      return CachedNetworkImage(
        imageUrl: urls.first,
        fit: BoxFit.cover,
        errorWidget: (_, _, _) => Container(
          color: colorScheme.surfaceContainerHighest,
          child: Icon(
            Icons.set_meal_outlined,
            color: colorScheme.onSurfaceVariant,
          ),
        ),
      );
    }
    // 2+ images — simple 2x2 grid, with blanks for missing slots.
    final tiles = <Widget>[];
    for (var i = 0; i < 4; i++) {
      if (i < urls.length) {
        tiles.add(CachedNetworkImage(
          imageUrl: urls[i],
          fit: BoxFit.cover,
          errorWidget: (_, _, _) =>
              ColoredBox(color: colorScheme.surfaceContainerHighest),
        ));
      } else {
        tiles.add(ColoredBox(color: colorScheme.surfaceContainerHighest));
      }
    }
    return Column(
      children: [
        Expanded(
          child: Row(
            children: [
              Expanded(child: tiles[0]),
              const SizedBox(width: 1),
              Expanded(child: tiles[1]),
            ],
          ),
        ),
        const SizedBox(height: 1),
        Expanded(
          child: Row(
            children: [
              Expanded(child: tiles[2]),
              const SizedBox(width: 1),
              Expanded(child: tiles[3]),
            ],
          ),
        ),
      ],
    );
  }
}

class _RecipeCountBadge extends StatelessWidget {
  final int count;
  const _RecipeCountBadge({required this.count});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: colorScheme.secondaryContainer,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        '$count',
        style: textTheme.labelSmall?.copyWith(
          color: colorScheme.onSecondaryContainer,
          fontWeight: FontWeight.w600,
          fontSize: 10,
        ),
      ),
    );
  }
}
