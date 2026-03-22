import 'package:flutter/material.dart';

import '../../core/di/injection.dart';
import '../../features/shopping_cart/models/shopping_list.dart';
import '../../features/shopping_cart/services/shopping_cart_service.dart';

/// Shows a bottom sheet letting the user switch their default shopping list.
Future<void> showDefaultChangeSheet({
  required BuildContext context,
  required List<ShoppingList> lists,
  required String currentListId,
}) {
  return showModalBottomSheet<void>(
    context: context,
    builder: (ctx) => _DefaultChangeSheet(
      lists: lists,
      currentListId: currentListId,
    ),
  );
}

class _DefaultChangeSheet extends StatelessWidget {
  final List<ShoppingList> lists;
  final String currentListId;

  const _DefaultChangeSheet({
    required this.lists,
    required this.currentListId,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final otherLists = lists.where((l) => l.id != currentListId).toList();

    return SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: Text(
              'Switch Default List',
              style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Text(
              'Future items will be added to the list you choose.',
              style: textTheme.bodySmall?.copyWith(
                color: colorScheme.onSurfaceVariant,
              ),
            ),
          ),
          const SizedBox(height: 8),
          ...otherLists.map((list) {
            final listName = list.name.isEmpty ? 'Shopping List' : list.name;
            return ListTile(
              leading: const Icon(Icons.shopping_cart_outlined),
              title: Text(listName),
              subtitle: Text('${list.uncheckedCount} items'),
              onTap: () {
                final service = getIt<ShoppingCartService>();
                service.setDefaultShoppingList(list.id);
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text('$listName is now your default list'),
                  ),
                );
              },
            );
          }),
          const SizedBox(height: 8),
        ],
      ),
    );
  }
}
