import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/di/injection.dart';
import '../../../core/state/mutation_failure_copy.dart';
import '../../../core/state/mutation_snackbar.dart';
import '../models/pantry_ingredient.dart';
import '../providers/pantry_provider.dart';
import '../services/pantry_service.dart';
import '../widgets/fuzzy_expiry_text.dart';
import '../widgets/pantry_filter_bar.dart';
import '../widgets/pantry_ingredient_tile.dart';

/// rp-3 — Pantry list is now a Riverpod consumer. `PantryService` is
/// stateless (no `_current` cache, no `StreamController`); all state
/// flows through `defaultPantryProvider`, which invalidates on
/// `PantryItem*` bus events.
class PantryListScreen extends ConsumerStatefulWidget {
  const PantryListScreen({super.key});

  @override
  ConsumerState<PantryListScreen> createState() => _PantryListScreenState();
}

class _PantryListScreenState extends ConsumerState<PantryListScreen> {
  Set<String> _selectedCategories = <String>{};

  PantryService get _service => getIt<PantryService>();

  List<PantryIngredient> _visibleItems(List<PantryIngredient> items) {
    if (_selectedCategories.isEmpty) return items;
    return items
        .where((i) =>
            i.category != null && _selectedCategories.contains(i.category))
        .toList();
  }

  (List<PantryIngredient>, List<PantryIngredient>, List<PantryIngredient>)
      _group(List<PantryIngredient> items) {
    final expiringSoon = <PantryIngredient>[];
    final fresh = <PantryIngredient>[];
    final noDate = <PantryIngredient>[];
    for (final item in items) {
      final exp = fuzzyExpiry(item.expiresAt).urgency;
      switch (exp) {
        case ExpiryUrgency.expired:
        case ExpiryUrgency.today:
        case ExpiryUrgency.tomorrow:
        case ExpiryUrgency.soon:
          expiringSoon.add(item);
          break;
        case ExpiryUrgency.fresh:
        case ExpiryUrgency.plenty:
          fresh.add(item);
          break;
        case ExpiryUrgency.none:
          noDate.add(item);
          break;
      }
    }
    int byExpiry(PantryIngredient a, PantryIngredient b) {
      final ax = a.expiresAt;
      final bx = b.expiresAt;
      if (ax == null && bx == null) return 0;
      if (ax == null) return 1;
      if (bx == null) return -1;
      return ax.compareTo(bx);
    }

    expiringSoon.sort(byExpiry);
    fresh.sort(byExpiry);
    noDate.sort((a, b) =>
        (a.ingredientName ?? '').compareTo(b.ingredientName ?? ''));
    return (expiringSoon, fresh, noDate);
  }

  void _onUseMeUp(PantryIngredient item) {
    final name = item.ingredientName;
    if (name == null || name.isEmpty) return;
    context.push('/search?q=${Uri.encodeQueryComponent(name)}');
  }

  /// Delete + undo-success-snackbar path. The undo action is a
  /// success-flow UX affordance (rp-3 Design Principle #4), distinct
  /// from `showMutationFailureSnackbar`.
  Future<void> _handleDelete(PantryIngredient item) async {
    final pantryId = item.pantryId;
    final removed = item;
    try {
      await _service.deletePantryIngredient(pantryId, item.ingredientId);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Removed ${item.ingredientName ?? 'item'}'),
          duration: const Duration(seconds: 4),
          action: SnackBarAction(
            label: 'Undo',
            onPressed: () async {
              try {
                await _service.addPantryIngredient(pantryId, {
                  'ingredient_id': removed.ingredientId,
                  'quantity_display': removed.quantityDisplay,
                  'unit_display': removed.unitDisplay,
                  'quantity_normalized': removed.quantityNormalized,
                  'unit_normalized': removed.unitNormalized,
                  if (removed.storageLocation != null)
                    'storage_location': removed.storageLocation,
                  if (removed.expiresAt != null)
                    'expires_at': removed.expiresAt!.toIso8601String(),
                });
              } catch (_) {
                if (!mounted) return;
                showMutationFailureSnackbar(
                  context,
                  MutationType.addPantryItem,
                  () => _handleDelete(item),
                );
              }
            },
          ),
        ),
      );
    } catch (_) {
      if (!mounted) return;
      showMutationFailureSnackbar(
        context,
        MutationType.deletePantryItem,
        () => _handleDelete(item),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Pantry')),
      floatingActionButton: FloatingActionButton(
        onPressed: () => context.push('/pantry/add'),
        tooltip: 'Add item',
        child: const Icon(Icons.add),
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    final pantryAsync = ref.watch(defaultPantryProvider);
    return pantryAsync.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (error, _) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(
            'Could not load your pantry. Pull to retry.',
            textAlign: TextAlign.center,
          ),
        ),
      ),
      data: (pantry) {
        if (pantry.items.isEmpty) return const _EmptyState();
        final categories = <String>{
          for (final item in pantry.items)
            if (item.category != null && item.category!.isNotEmpty)
              item.category!,
        }.toList()
          ..sort();

        final (expiringSoon, fresh, noDate) = _group(_visibleItems(pantry.items));

        return RefreshIndicator(
          onRefresh: () async =>
              ref.refresh(defaultPantryProvider.future),
          child: ListView(
            padding: const EdgeInsets.only(bottom: 80),
            children: [
              PantryFilterBar(
                availableCategories: categories,
                selectedCategories: _selectedCategories,
                onChanged: (next) =>
                    setState(() => _selectedCategories = next),
              ),
              _section(context, 'Expiring Soon', expiringSoon,
                  showUseMeUp: true),
              _section(context, 'Fresh', fresh),
              _section(context, 'No Date', noDate),
            ],
          ),
        );
      },
    );
  }

  Widget _section(
    BuildContext context,
    String title,
    List<PantryIngredient> items, {
    bool showUseMeUp = false,
  }) {
    if (items.isEmpty) return const SizedBox.shrink();
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
          child: Text(
            title,
            style: theme.textTheme.titleSmall?.copyWith(
              letterSpacing: 0.5,
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ),
        for (final item in items)
          Dismissible(
            key: Key('pantry-${item.pantryId}-${item.ingredientId}'),
            direction: DismissDirection.endToStart,
            background: Container(
              alignment: Alignment.centerRight,
              padding: const EdgeInsets.only(right: 16),
              color: theme.colorScheme.error,
              child: Icon(Icons.delete, color: theme.colorScheme.onError),
            ),
            onDismissed: (_) => _handleDelete(item),
            child: PantryIngredientTile(
              item: item,
              onTap: () =>
                  context.push('/pantry/edit/${item.ingredientId}'),
              onUseMeUp: showUseMeUp
                  ? () => _onUseMeUp(item)
                  : null,
            ),
          ),
      ],
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.kitchen, size: 72),
            const SizedBox(height: 16),
            Text(
              'Your pantry is empty.',
              style: theme.textTheme.titleMedium,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 4),
            Text(
              'Start shopping, or tap + to add something.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}
