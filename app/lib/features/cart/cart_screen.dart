import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../core/di/injection.dart';
import '../../shared/widgets/empty_state.dart';
import '../shopping_cart/models/shopping_list.dart';
import '../shopping_cart/services/shopping_cart_service.dart';

/// Cart tab — shows all shopping lists owned by or shared with the current user.
class CartScreen extends StatefulWidget {
  const CartScreen({super.key});

  @override
  State<CartScreen> createState() => _CartScreenState();
}

class _CartScreenState extends State<CartScreen> {
  final _service = getIt<ShoppingCartService>();

  List<ShoppingList> _lists = [];
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadLists();
  }

  Future<void> _loadLists() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final lists = await _service.getShoppingLists();
      if (mounted) {
        setState(() {
          _lists = lists;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Could not load shopping lists. Please try again.';
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _createList() async {
    final nameController = TextEditingController();
    final created = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(
          'New Shopping List',
          style: GoogleFonts.playfairDisplay(fontWeight: FontWeight.w600),
        ),
        content: TextField(
          controller: nameController,
          autofocus: true,
          decoration: const InputDecoration(
            hintText: 'List name (e.g. Weekly Groceries)',
            border: OutlineInputBorder(),
          ),
          textCapitalization: TextCapitalization.sentences,
          onSubmitted: (_) => Navigator.of(context).pop(true),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Create'),
          ),
        ],
      ),
    );

    if (created != true || !mounted) return;

    final name = nameController.text.trim();
    if (name.isEmpty) return;

    try {
      final list = await _service.createShoppingList(name);
      if (mounted) {
        context.push('/shopping-lists/${list.id}');
        _loadLists();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to create shopping list.')),
        );
      }
    }
  }

  Future<void> _joinList() async {
    final codeController = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(
          'Join a Shopping List',
          style: GoogleFonts.playfairDisplay(fontWeight: FontWeight.w600),
        ),
        content: TextField(
          controller: codeController,
          autofocus: true,
          decoration: const InputDecoration(
            hintText: 'Enter share code',
            border: OutlineInputBorder(),
          ),
          textCapitalization: TextCapitalization.characters,
          onSubmitted: (_) => Navigator.of(context).pop(true),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Join'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;

    final code = codeController.text.trim();
    if (code.isEmpty) return;

    try {
      final list = await _service.joinList(code);
      if (mounted) {
        context.push('/shopping-lists/${list.id}');
        _loadLists();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Invalid share code or list not found.')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(
        title: Text(
          'Cart',
          style: GoogleFonts.playfairDisplay(fontWeight: FontWeight.w600),
        ),
        actions: [
          PopupMenuButton<String>(
            onSelected: (value) {
              if (value == 'join') _joinList();
            },
            itemBuilder: (context) => [
              const PopupMenuItem(
                value: 'join',
                child: Row(
                  children: [
                    Icon(Icons.link, size: 20),
                    SizedBox(width: 12),
                    Text('Join a list'),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
      body: _buildBody(colorScheme, textTheme),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _createList,
        icon: const Icon(Icons.add),
        label: const Text('New List'),
      ),
    );
  }

  Widget _buildBody(ColorScheme colorScheme, TextTheme textTheme) {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.error_outline, size: 64, color: colorScheme.error),
              const SizedBox(height: 16),
              Text(_error!, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: _loadLists,
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (_lists.isEmpty) {
      return const EmptyStateWidget(
        icon: Icons.shopping_cart_outlined,
        title: 'No shopping lists yet',
        subtitle: 'Tap + to create your first list',
      );
    }

    return RefreshIndicator(
      onRefresh: _loadLists,
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 100),
        itemCount: _lists.length,
        separatorBuilder: (_, __) => const SizedBox(height: 8),
        itemBuilder: (context, index) {
          final list = _lists[index];
          return _ShoppingListCard(
            list: list,
            onTap: () => context.push('/shopping-lists/${list.id}'),
          );
        },
      ),
    );
  }
}

class _ShoppingListCard extends StatelessWidget {
  final ShoppingList list;
  final VoidCallback onTap;

  const _ShoppingListCard({required this.list, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    final total = list.items.length;
    final checked = list.items.where((i) => i.isChecked).length;
    final unchecked = total - checked;

    return Card(
      elevation: 0,
      color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: colorScheme.primaryContainer,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(
                  Icons.shopping_cart_outlined,
                  color: colorScheme.onPrimaryContainer,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      list.name.isEmpty ? 'Shopping List' : list.name,
                      style: textTheme.bodyLarge?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      unchecked == 0
                          ? (total == 0 ? 'Empty' : 'All done!')
                          : '$unchecked item${unchecked == 1 ? '' : 's'} remaining',
                      style: textTheme.bodySmall?.copyWith(
                        color: colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
              if (list.isShared)
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: Icon(
                    Icons.people_outline,
                    size: 18,
                    color: colorScheme.primary,
                  ),
                ),
              Icon(
                Icons.chevron_right,
                color: colorScheme.onSurfaceVariant,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
