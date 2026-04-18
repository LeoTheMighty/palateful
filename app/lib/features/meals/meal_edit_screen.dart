import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'providers/meals_provider.dart';

/// Placeholder shipped with mcv-4 — drag-to-reorder + Add Recipe FAB land
/// in mcv-6. Route wired now so the eventual Edit button on
/// MealDetailScreen has a target.
class MealEditScreen extends ConsumerWidget {
  final String mealId;
  const MealEditScreen({super.key, required this.mealId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final mealAsync = ref.watch(mealByIdProvider(mealId));
    return Scaffold(
      appBar: AppBar(title: const Text('Edit meal')),
      body: mealAsync.when(
        data: (meal) => Center(
          child: Text(
            'Edit UX for "${meal.name}" lands in mcv-6.',
            style: const TextStyle(color: Colors.black54),
          ),
        ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, _) =>
            Center(child: Text('Failed to load meal: $err')),
      ),
    );
  }
}
