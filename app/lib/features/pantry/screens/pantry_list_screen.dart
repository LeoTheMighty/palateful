import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/di/injection.dart';
import '../models/pantry.dart';
import '../models/pantry_ingredient.dart';
import '../services/pantry_service.dart';
import '../widgets/fuzzy_expiry_text.dart';
import '../widgets/pantry_filter_bar.dart';
import '../widgets/pantry_ingredient_tile.dart';

/// Pantry list grouped by expiry urgency (Expiring Soon / Fresh / No Date).
/// The emotional hook: "what's about to go bad?"
class PantryListScreen extends StatefulWidget {
  const PantryListScreen({super.key});

  @override
  State<PantryListScreen> createState() => _PantryListScreenState();
}

class _PantryListScreenState extends State<PantryListScreen> {
  final PantryService _service = getIt<PantryService>();

  Pantry? _pantry;
  bool _isLoading = true;
  String? _error;
  Set<String> _selectedCategories = <String>{};
  StreamSubscription<Pantry?>? _sub;

  @override
  void initState() {
    super.initState();
    _pantry = _service.current;
    _isLoading = _pantry == null;
    _sub = _service.pantryStream.listen((p) {
      if (!mounted) return;
      setState(() {
        _pantry = p;
        _isLoading = false;
      });
    });
    _load();
  }

  Future<void> _load() async {
    try {
      await _service.loadDefaultPantry();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _error = 'Could not load your pantry. Pull to retry.';
      });
    }
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }

  List<PantryIngredient> _visibleItems() {
    final items = _pantry?.items ?? const <PantryIngredient>[];
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
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Undo failed')),
                );
              }
            },
          ),
        ),
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not remove item')),
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
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null && (_pantry?.items.isEmpty ?? true)) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(_error!, textAlign: TextAlign.center),
        ),
      );
    }
    final pantry = _pantry;
    if (pantry == null || pantry.items.isEmpty) {
      return const _EmptyState();
    }

    final categories = <String>{
      for (final item in pantry.items)
        if (item.category != null && item.category!.isNotEmpty) item.category!,
    }.toList()
      ..sort();

    final (expiringSoon, fresh, noDate) = _group(_visibleItems());

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.only(bottom: 80),
        children: [
          PantryFilterBar(
            availableCategories: categories,
            selectedCategories: _selectedCategories,
            onChanged: (next) => setState(() => _selectedCategories = next),
          ),
          _section(context, 'Expiring Soon', expiringSoon),
          _section(context, 'Fresh', fresh),
          _section(context, 'No Date', noDate),
        ],
      ),
    );
  }

  Widget _section(
    BuildContext context,
    String title,
    List<PantryIngredient> items,
  ) {
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
