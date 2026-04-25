import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'home_selection_controller.dart';

/// Bottom-docked bulk bar. Primary slot is context-sensitive (Create
/// Meal / `Add to "<name>"` / disabled-with-reason). Secondary slots are
/// `Add to…` / `Move to…` (recipe-only) and Archive (always enabled
/// when the selection is non-empty).
///
/// Mounted in `Scaffold.bottomNavigationBar` (not Stack/Positioned) —
/// home uses sliver-backed `CustomScrollView` fragments and the slot is
/// free today, so `bottomNavigationBar` avoids gesture-nav clipping on
/// Android without a `Positioned+SafeArea` dance.
class HomeBulkActionBar extends ConsumerWidget {
  /// Resolved display name for the Meal currently selected in the
  /// "Add to Meal" branch. Null in every other shape; the bar will
  /// either render a disabled/Create state or swap to a generic
  /// "Add to Meal" label.
  final String? selectedMealName;

  /// Disables every bar button while a bulk op is inflight. Wired by
  /// hmp-3; hmp-2 always passes false.
  final bool isWorking;

  /// hmp-3 callbacks — in hmp-2 all three are no-op stubs.
  final VoidCallback? onCreateMeal;
  final VoidCallback? onAddToMeal;
  final VoidCallback? onArchive;

  /// recipe-bulk-org-1 callbacks. `Add to…` and `Move to…` open the
  /// shared `BookPickerSheet`; the bar itself stays UI-only.
  final VoidCallback? onAddToBook;
  final VoidCallback? onMoveToBook;

  const HomeBulkActionBar({
    super.key,
    this.selectedMealName,
    this.isWorking = false,
    this.onCreateMeal,
    this.onAddToMeal,
    this.onArchive,
    this.onAddToBook,
    this.onMoveToBook,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(homeSelectionProvider);
    if (!state.isActive) return const SizedBox.shrink();
    final action = resolvePrimaryAction(state.shape);
    final colorScheme = Theme.of(context).colorScheme;

    // Move/Add to Book apply to recipes (single-FK swap on the
    // `recipe_book_id` column). Hide them when the selection has any
    // Meals — Meals don't live in books.
    final showBookActions = state.selectedRecipeIds.isNotEmpty &&
        state.selectedMealIds.isEmpty;

    return Material(
      color: colorScheme.surfaceContainerHighest,
      elevation: 4,
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (isWorking)
              LinearProgressIndicator(
                minHeight: 2,
                color: colorScheme.primary,
                backgroundColor: colorScheme.surfaceContainerHighest,
              ),
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
              child: Row(
                children: [
                  Expanded(
                    child: _PrimarySlot(
                      action: action,
                      selectedMealName: selectedMealName,
                      isWorking: isWorking,
                      onCreateMeal: onCreateMeal,
                      onAddToMeal: onAddToMeal,
                    ),
                  ),
                  if (showBookActions) ...[
                    const SizedBox(width: 8),
                    _BookActionButton(
                      label: 'Add to',
                      icon: Icons.add_box_outlined,
                      enabled: !isWorking,
                      onPressed: onAddToBook,
                    ),
                    const SizedBox(width: 8),
                    _BookActionButton(
                      label: 'Move to',
                      icon: Icons.drive_file_move_outlined,
                      enabled: !isWorking,
                      onPressed: onMoveToBook,
                    ),
                  ],
                  const SizedBox(width: 8),
                  _ArchiveButton(
                    enabled: !isWorking && state.totalSelected > 0,
                    onPressed: onArchive,
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

class _PrimarySlot extends StatelessWidget {
  final BulkPrimaryAction action;
  final String? selectedMealName;
  final bool isWorking;
  final VoidCallback? onCreateMeal;
  final VoidCallback? onAddToMeal;

  const _PrimarySlot({
    required this.action,
    required this.selectedMealName,
    required this.isWorking,
    required this.onCreateMeal,
    required this.onAddToMeal,
  });

  @override
  Widget build(BuildContext context) {
    switch (action) {
      case EmptyAction():
        return const SizedBox.shrink();
      case CreateMealAction():
        return Semantics(
          label: 'Create Meal',
          button: true,
          child: FilledButton.icon(
            onPressed: isWorking ? null : onCreateMeal,
            icon: const Icon(Icons.set_meal_outlined),
            label: const Text('Create Meal'),
          ),
        );
      case AddToMealAction():
        final label = selectedMealName == null || selectedMealName!.isEmpty
            ? 'Add to Meal'
            : 'Add to "${selectedMealName!}"';
        return Semantics(
          label: label,
          button: true,
          child: FilledButton.icon(
            onPressed: isWorking ? null : onAddToMeal,
            icon: const Icon(Icons.playlist_add),
            label: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        );
      case DisabledAction(:final reason):
        return Tooltip(
          message: reason,
          preferBelow: false,
          child: Semantics(
            label: reason,
            button: true,
            enabled: false,
            child: FilledButton.icon(
              onPressed: null,
              icon: const Icon(Icons.block),
              label: const Text('Bulk action unavailable'),
            ),
          ),
        );
    }
  }
}

class _BookActionButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool enabled;
  final VoidCallback? onPressed;

  const _BookActionButton({
    required this.label,
    required this.icon,
    required this.enabled,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: '$label book',
      button: true,
      enabled: enabled,
      child: OutlinedButton.icon(
        onPressed: enabled ? onPressed : null,
        icon: Icon(icon),
        label: Text(label),
      ),
    );
  }
}

class _ArchiveButton extends StatelessWidget {
  final bool enabled;
  final VoidCallback? onPressed;

  const _ArchiveButton({required this.enabled, required this.onPressed});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Semantics(
      label: 'Archive selected',
      button: true,
      enabled: enabled,
      child: OutlinedButton.icon(
        onPressed: enabled ? onPressed : null,
        icon: Icon(Icons.archive_outlined, color: colorScheme.error),
        label: Text('Archive',
            style: TextStyle(color: colorScheme.error)),
      ),
    );
  }
}
