import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/theme/theme.dart';
import '../models/meal.dart';
import 'component_collage_hero.dart';

/// Canonical "N recipes" label for any surface that shows a meal's
/// component count (meal_tile, calendar event tiles, recurring plans
/// rows, detail sheets). Single source of truth — do not inline the
/// format string.
String kMealComponentCountLabel(int n) => '$n recipes';

/// Meal grid tile v2 (hmp-1). Adds a "Meal" accent pill, a 2-px accent
/// border, a component-name chip row under the name (resolved via an
/// in-memory join supplied by the caller), a favorite-star overlay that
/// matches `RecipeCard`, and a selected-state checkmark for selection
/// mode (hmp-2).
///
/// Backward-compatibility: every new constructor parameter is optional,
/// so existing callers (book-detail grid, search results) keep the
/// pre-epic shape — when `componentNameResolver` is null the chip row
/// falls back to the "(N recipes)" label so no caller loses count
/// information.
class MealTile extends StatelessWidget {
  final MealSummary meal;
  final VoidCallback onTap;
  final VoidCallback? onLongPress;

  /// Resolves a component recipe id to a display name. When null (or
  /// when every lookup returns null) the chip row renders the
  /// "(N recipes)" backward-compat label instead of component names.
  final String? Function(String recipeId)? componentNameResolver;

  /// Is this Meal currently favorited? Only consulted when
  /// [onFavoriteToggle] is non-null.
  final bool isFavorited;

  /// When non-null a heart-overlay button renders in the top-right and
  /// fires this callback on tap. Callers handle optimistic update +
  /// error rollback themselves.
  final VoidCallback? onFavoriteToggle;

  /// When true the collage shows a centered checkmark overlay + a
  /// translucent dim layer (selection-mode visual).
  final bool selected;

  const MealTile({
    super.key,
    required this.meal,
    required this.onTap,
    this.onLongPress,
    this.componentNameResolver,
    this.isFavorited = false,
    this.onFavoriteToggle,
    this.selected = false,
  });

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final colorScheme = Theme.of(context).colorScheme;

    final accent = colorScheme.primary.withValues(alpha: 0.6);
    final chipLine = _buildChipLine();

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: accent, width: 2),
      ),
      child: InkWell(
        onTap: onTap,
        onLongPress: onLongPress,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              height: 180,
              width: double.infinity,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  ComponentCollageHero(
                    components: _buildComponentsFromSummary(meal),
                  ),
                  const Positioned(
                    top: 8,
                    left: 8,
                    child: _MealPill(),
                  ),
                  if (onFavoriteToggle != null)
                    Positioned(
                      top: 4,
                      right: 4,
                      child: _FavoriteOverlay(
                        isFavorited: isFavorited,
                        onToggle: onFavoriteToggle!,
                      ),
                    ),
                  if (selected) const _SelectedOverlay(),
                ],
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
                  const SizedBox(height: 6),
                  Text(
                    chipLine,
                    key: const ValueKey('meal-tile-chips'),
                    style: textTheme.bodySmall?.copyWith(
                      color: colorScheme.onSurfaceVariant,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _buildChipLine() {
    if (componentNameResolver == null) {
      // Backward-compat — callers that haven't migrated keep the
      // decorative count label.
      return '(${kMealComponentCountLabel(meal.componentCount)})';
    }
    final ids = meal.componentRecipeIds;
    if (ids.isEmpty) {
      return '(${kMealComponentCountLabel(meal.componentCount)})';
    }
    final resolvedNames = <String>[];
    var hadUnknown = false;
    for (final id in ids) {
      final name = componentNameResolver!(id);
      if (name == null || name.isEmpty) {
        hadUnknown = true;
      } else {
        resolvedNames.add(name);
      }
    }
    if (resolvedNames.isEmpty) {
      return '(${kMealComponentCountLabel(meal.componentCount)})';
    }
    final shown = resolvedNames.take(2).toList();
    final remaining = resolvedNames.length - shown.length;
    var line = shown.join(' · ');
    if (remaining > 0) {
      line = '$line · +$remaining';
    }
    if (hadUnknown) {
      line = '$line · (archived)';
    }
    return line;
  }
}

class _MealPill extends StatelessWidget {
  const _MealPill();

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Semantics(
      label: 'Meal',
      container: true,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.88),
          borderRadius: BorderRadius.circular(6),
          boxShadow: const [
            BoxShadow(
              color: Color(0x40000000),
              blurRadius: 4,
              offset: Offset(0, 1),
            ),
          ],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.layers_outlined, size: 14, color: Colors.black87),
            const SizedBox(width: 4),
            Text(
              'Meal',
              style: textTheme.labelSmall?.copyWith(
                color: Colors.black87,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _FavoriteOverlay extends StatelessWidget {
  final bool isFavorited;
  final VoidCallback onToggle;

  const _FavoriteOverlay({required this.isFavorited, required this.onToggle});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Semantics(
      label: isFavorited ? 'Unfavorite' : 'Favorite',
      button: true,
      child: GestureDetector(
        onTap: () {
          HapticFeedback.selectionClick();
          onToggle();
        },
        child: Container(
          padding: const EdgeInsets.all(6),
          decoration: const BoxDecoration(
            color: Color(0x4D000000),
            shape: BoxShape.circle,
          ),
          child: Icon(
            isFavorited ? Icons.favorite : Icons.favorite_border,
            size: 18,
            color: isFavorited ? AppColors.favorite : colorScheme.surface,
          ),
        ),
      ),
    );
  }
}

class _SelectedOverlay extends StatelessWidget {
  const _SelectedOverlay();

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return IgnorePointer(
      child: Container(
        decoration: BoxDecoration(
          color: colorScheme.primary.withValues(alpha: 0.35),
        ),
        child: Center(
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
