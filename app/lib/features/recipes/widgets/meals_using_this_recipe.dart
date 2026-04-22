// md-6: "Used in these Meals" row on the recipe detail screen.
// rmc-2: migrated from `StatefulWidget + FutureBuilder` to
// `ConsumerWidget + ref.watch(usedInMealsProvider)` so the row reacts
// to meal-component mutations without a remount.
//
// Load-bearing invariant preserved: empty / error → `SizedBox.shrink()`
// (no header, no empty state). Recipe detail rendering stays bit-
// identical to pre-epic for any user with zero Meals referencing the
// recipe, and never blocks the screen on a failed cross-lookup call.
//
// NOT mounted on `public_recipe_screen.dart` by design — leaking
// private Meal names to unauthenticated viewers is a privacy regression
// (see epic's Design Principle 8).

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../meals/models/meal.dart';
import '../providers/used_in_meals_provider.dart';

class MealsUsingThisRecipe extends ConsumerWidget {
  final String recipeId;

  const MealsUsingThisRecipe({super.key, required this.recipeId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(usedInMealsProvider(recipeId));
    // Preserve previous data across refetches (AsyncValue.value guard —
    // Foundation loading-flicker pattern). During refetch, render the
    // last-known list instead of flashing back to the shimmer.
    final previous = async.value;

    if (async.isLoading && previous == null) {
      return const _ShimmerRow();
    }
    final data = previous;
    // Error OR empty → hide entirely. Section header does NOT render.
    if (data == null || data.isEmpty) {
      return const SizedBox.shrink();
    }
    return _MealsRow(meals: data);
  }
}

class _ShimmerRow extends StatelessWidget {
  const _ShimmerRow();

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return SizedBox(
      height: 150,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        itemCount: 3,
        separatorBuilder: (_, _) => const SizedBox(width: 12),
        itemBuilder: (_, _) => Container(
          width: 140,
          height: 120,
          decoration: BoxDecoration(
            color: colorScheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
    );
  }
}

class _MealsRow extends StatelessWidget {
  final List<MealSummary> meals;
  const _MealsRow({required this.meals});

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final headerText = meals.length == 1
        ? 'Used in 1 meal'
        : 'Used in ${meals.length} meals';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
          child: Text(
            headerText,
            style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
          ),
        ),
        SizedBox(
          height: 150,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            itemCount: meals.length,
            separatorBuilder: (_, _) => const SizedBox(width: 12),
            itemBuilder: (context, i) => _MealCard(meal: meals[i]),
          ),
        ),
        const SizedBox(height: 16),
      ],
    );
  }
}

class _MealCard extends StatelessWidget {
  final MealSummary meal;
  const _MealCard({required this.meal});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final imageUrl = meal.componentImageUrls.isNotEmpty
        ? meal.componentImageUrls.first
        : null;
    return InkWell(
      onTap: () => context.push('/meals/${meal.id}'),
      child: SizedBox(
        width: 140,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: SizedBox(
                width: 140,
                height: 120,
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    imageUrl != null
                        ? CachedNetworkImage(
                            imageUrl: imageUrl,
                            fit: BoxFit.cover,
                            errorWidget: (_, _, _) =>
                                ColoredBox(color: colorScheme.surfaceContainerHighest),
                          )
                        : ColoredBox(color: colorScheme.surfaceContainerHighest),
                    Positioned(
                      right: 6,
                      bottom: 6,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: colorScheme.secondaryContainer,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          '${meal.componentCount}',
                          style: textTheme.labelSmall?.copyWith(
                            color: colorScheme.onSecondaryContainer,
                            fontWeight: FontWeight.w600,
                            fontSize: 10,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 4),
            Text(
              meal.name,
              style: textTheme.bodySmall?.copyWith(fontWeight: FontWeight.w500),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
  }
}
