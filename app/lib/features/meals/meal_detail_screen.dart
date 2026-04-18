import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'providers/meals_provider.dart';

/// Placeholder shipped with mcv-4 — full implementation lands in mcv-6.
/// Keeping the route wired now so mcv-5's Create Meal flow can navigate
/// to it on success without a router-wiring round-trip.
class MealDetailScreen extends ConsumerWidget {
  final String mealId;
  const MealDetailScreen({super.key, required this.mealId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final mealAsync = ref.watch(mealByIdProvider(mealId));
    return Scaffold(
      appBar: AppBar(
        title: mealAsync.when(
          data: (m) => Text(m.name),
          loading: () => const Text('Meal'),
          error: (_, _) => const Text('Meal'),
        ),
      ),
      body: mealAsync.when(
        data: (meal) => Center(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  meal.name,
                  style: Theme.of(context).textTheme.titleLarge,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  '${meal.componentCount} recipes',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
                const SizedBox(height: 12),
                const Text('Full Meal detail lands in mcv-6.',
                    style: TextStyle(color: Colors.black54)),
              ],
            ),
          ),
        ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, _) => Center(
          child: Text('Failed to load meal: $err'),
        ),
      ),
    );
  }
}
