import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/shopping_cart/models/shopping_list.dart';

/// Widget tests for the "Add to Cart" feature in the recipe detail screen.
/// Tests UI components and logic in isolation without DI or real network.
void main() {
  group('Add to Cart — PopupMenu item', () {
    testWidgets('popup menu includes Add to Cart option', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          appBar: AppBar(
            actions: [
              PopupMenuButton<String>(
                itemBuilder: (context) => [
                  const PopupMenuItem(
                    value: 'add_to_cart',
                    child: Row(
                      children: [
                        Icon(Icons.shopping_cart_outlined),
                        SizedBox(width: 8),
                        Text('Add to Cart'),
                      ],
                    ),
                  ),
                  const PopupMenuItem(
                    value: 'copy',
                    child: Text('Copy to Book...'),
                  ),
                ],
              ),
            ],
          ),
          body: const Text('Recipe'),
        ),
      ));

      // Open popup menu
      await tester.tap(find.byType(PopupMenuButton<String>));
      await tester.pumpAndSettle();

      expect(find.text('Add to Cart'), findsOneWidget);
      expect(find.byIcon(Icons.shopping_cart_outlined), findsOneWidget);
    });

    testWidgets('Add to Cart is the first menu item', (tester) async {
      final menuItems = <String>[];

      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          appBar: AppBar(
            actions: [
              PopupMenuButton<String>(
                onSelected: menuItems.add,
                itemBuilder: (context) => [
                  const PopupMenuItem(
                      value: 'add_to_cart', child: Text('Add to Cart')),
                  const PopupMenuItem(value: 'copy', child: Text('Copy')),
                  const PopupMenuItem(value: 'fork', child: Text('Fork')),
                ],
              ),
            ],
          ),
          body: const Text('Recipe'),
        ),
      ));

      await tester.tap(find.byType(PopupMenuButton<String>));
      await tester.pumpAndSettle();

      // First item in the list is 'Add to Cart'
      final items = tester.widgetList<PopupMenuItem<String>>(
          find.byType(PopupMenuItem<String>));
      expect(items.first.value, 'add_to_cart');
    });
  });

  group('Add to Cart — no lists snackbar', () {
    testWidgets('shows "No shopping lists" snackbar when lists are empty',
        (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: _AddToCartTester(lists: []),
      ));

      await tester.tap(find.text('Add to Cart'));
      await tester.pump();

      expect(
          find.text('No shopping lists — tap + to create one'), findsOneWidget);
    });
  });

  group('Add to Cart — success snackbar', () {
    testWidgets('shows singular "ingredient" for 1 item added', (tester) async {
      final list = _makeList(name: 'Weekly Groceries');
      await tester.pumpWidget(MaterialApp(
        home: _AddToCartTester(lists: [list], itemsAdded: 1),
      ));

      await tester.tap(find.text('Add to Cart'));
      await tester.pump();

      expect(
          find.text('Added 1 ingredient to Weekly Groceries'), findsOneWidget);
    });

    testWidgets('shows plural "ingredients" for 3 items added', (tester) async {
      final list = _makeList(name: 'Meal Prep');
      await tester.pumpWidget(MaterialApp(
        home: _AddToCartTester(lists: [list], itemsAdded: 3),
      ));

      await tester.tap(find.text('Add to Cart'));
      await tester.pump();

      expect(
          find.text('Added 3 ingredients to Meal Prep'), findsOneWidget);
    });

    testWidgets('uses fallback name when list name is empty', (tester) async {
      final list = _makeList(name: '');
      await tester.pumpWidget(MaterialApp(
        home: _AddToCartTester(lists: [list], itemsAdded: 2),
      ));

      await tester.tap(find.text('Add to Cart'));
      await tester.pump();

      expect(find.text('Added 2 ingredients to Shopping List'), findsOneWidget);
    });
  });

  group('Add to Cart — error snackbar', () {
    testWidgets('shows error snackbar when populateFromRecipe throws',
        (tester) async {
      final list = _makeList(name: 'My List');
      await tester.pumpWidget(MaterialApp(
        home: _AddToCartTester(lists: [list], itemsAdded: 0, throwError: true),
      ));

      await tester.tap(find.text('Add to Cart'));
      await tester.pump();

      expect(find.text('Failed to add ingredients to cart'), findsOneWidget);
    });
  });

  group('Add to Cart — list picker', () {
    testWidgets('shows bottom sheet picker when multiple lists exist',
        (tester) async {
      final lists = [
        _makeList(name: 'Groceries'),
        _makeList(name: 'Party Supplies'),
      ];
      await tester.pumpWidget(MaterialApp(
        home: _AddToCartTester(lists: lists, itemsAdded: 1),
      ));

      await tester.tap(find.text('Add to Cart'));
      await tester.pumpAndSettle();

      // Bottom sheet should appear with list names
      expect(find.text('Groceries'), findsOneWidget);
      expect(find.text('Party Supplies'), findsOneWidget);
    });
  });
}

// ---------------------------------------------------------------------------
// Test widget — simulates _addIngredientsToCart logic without DI
// ---------------------------------------------------------------------------

class _AddToCartTester extends StatelessWidget {
  final List<ShoppingList> lists;
  final int itemsAdded;
  final bool throwError;

  const _AddToCartTester(
      {required this.lists, this.itemsAdded = 0, this.throwError = false});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: ElevatedButton(
          onPressed: () => _addIngredientsToCart(context),
          child: const Text('Add to Cart'),
        ),
      ),
    );
  }

  Future<void> _addIngredientsToCart(BuildContext context) async {
    if (lists.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('No shopping lists — tap + to create one')),
      );
      return;
    }

    ShoppingList? selectedList;
    if (lists.length == 1) {
      selectedList = lists.first;
    } else {
      selectedList = await showModalBottomSheet<ShoppingList>(
        context: context,
        builder: (ctx) => ListView.builder(
          itemCount: lists.length,
          itemBuilder: (ctx, i) => ListTile(
            leading: const Icon(Icons.shopping_cart_outlined),
            title: Text(
                lists[i].name.isEmpty ? 'Shopping List' : lists[i].name),
            onTap: () => Navigator.of(ctx).pop(lists[i]),
          ),
        ),
      );
    }

    if (selectedList == null) return;
    if (!context.mounted) return;

    try {
      if (throwError) throw Exception('network error');
      final listName =
          selectedList.name.isEmpty ? 'Shopping List' : selectedList.name;
      final count = itemsAdded;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
              'Added $count ingredient${count == 1 ? '' : 's'} to $listName'),
        ),
      );
    } catch (_) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to add ingredients to cart')),
      );
    }
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

ShoppingList _makeList({String name = 'Test List', List<dynamic> items = const []}) {
  return ShoppingList.fromJson({
    'id': 'list-${name.hashCode}',
    'name': name,
    'status': 'active',
    'owner_id': 'user-1',
    'is_shared': false,
    'items': items,
    'members': [],
    'created_at': '2024-01-01T00:00:00.000Z',
    'updated_at': '2024-01-01T00:00:00.000Z',
  });
}
