import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../recipe_list_view.dart';

/// Single icon button placed in the home + recipe-book-detail headers
/// next to the existing sort/filter funnel. Swaps grid ↔ table icons
/// to mirror the active view, with a tooltip describing the *next*
/// state for screen-reader / hover affordance.
class RecipeListViewToggleButton extends ConsumerWidget {
  const RecipeListViewToggleButton({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final view = ref.watch(recipeListViewProvider);
    final isGrid = view == RecipeListView.grid;
    final tooltip =
        isGrid ? 'Switch to table view' : 'Switch to grid view';
    final icon = isGrid ? Icons.view_module : Icons.view_list;
    final colorScheme = Theme.of(context).colorScheme;

    return Tooltip(
      message: tooltip,
      child: Material(
        color: colorScheme.surfaceContainerHighest,
        shape: const CircleBorder(),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          key: const ValueKey('recipe_list_view_toggle'),
          onTap: () {
            HapticFeedback.selectionClick();
            ref.read(recipeListViewProvider.notifier).toggle();
          },
          customBorder: const CircleBorder(),
          child: Padding(
            padding: const EdgeInsets.all(10),
            child: Icon(icon, size: 20, color: colorScheme.onSurface),
          ),
        ),
      ),
    );
  }
}
