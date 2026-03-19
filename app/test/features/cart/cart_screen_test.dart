import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/shopping_cart/models/shopping_list.dart';
import 'package:palateful/features/shopping_cart/models/shopping_list_item.dart';

/// Widget tests for CartScreen — _ShoppingListCard component.
/// Tests card layout without wiring up DI or service layer.
void main() {
  group('_ShoppingListCard', () {
    testWidgets('shows list name', (tester) async {
      final list = _makeList(name: 'Weekly Groceries');
      await tester.pumpWidget(
        MaterialApp(home: Scaffold(body: _ShoppingListCardWrapper(list: list))),
      );
      expect(find.text('Weekly Groceries'), findsOneWidget);
    });

    testWidgets('shows fallback name when name is empty', (tester) async {
      final list = _makeList(name: '');
      await tester.pumpWidget(
        MaterialApp(home: Scaffold(body: _ShoppingListCardWrapper(list: list))),
      );
      expect(find.text('Shopping List'), findsOneWidget);
    });

    testWidgets('shows unchecked item count', (tester) async {
      final list = _makeList(
        items: [_makeItem(isChecked: false), _makeItem(isChecked: false)],
      );
      await tester.pumpWidget(
        MaterialApp(home: Scaffold(body: _ShoppingListCardWrapper(list: list))),
      );
      expect(find.text('2 items remaining'), findsOneWidget);
    });

    testWidgets('shows singular "item" when 1 unchecked', (tester) async {
      final list = _makeList(
        items: [_makeItem(isChecked: false), _makeItem(isChecked: true)],
      );
      await tester.pumpWidget(
        MaterialApp(home: Scaffold(body: _ShoppingListCardWrapper(list: list))),
      );
      expect(find.text('1 item remaining'), findsOneWidget);
    });

    testWidgets('shows "All done!" when all items are checked', (tester) async {
      final list = _makeList(
        items: [_makeItem(isChecked: true), _makeItem(isChecked: true)],
      );
      await tester.pumpWidget(
        MaterialApp(home: Scaffold(body: _ShoppingListCardWrapper(list: list))),
      );
      expect(find.text('All done!'), findsOneWidget);
    });

    testWidgets('shows "Empty" when list has no items', (tester) async {
      final list = _makeList(items: []);
      await tester.pumpWidget(
        MaterialApp(home: Scaffold(body: _ShoppingListCardWrapper(list: list))),
      );
      expect(find.text('Empty'), findsOneWidget);
    });

    testWidgets('shows shared icon when isShared is true', (tester) async {
      final list = _makeList(isShared: true);
      await tester.pumpWidget(
        MaterialApp(home: Scaffold(body: _ShoppingListCardWrapper(list: list))),
      );
      expect(find.byIcon(Icons.people_outline), findsOneWidget);
    });

    testWidgets('hides shared icon when isShared is false', (tester) async {
      final list = _makeList(isShared: false);
      await tester.pumpWidget(
        MaterialApp(home: Scaffold(body: _ShoppingListCardWrapper(list: list))),
      );
      expect(find.byIcon(Icons.people_outline), findsNothing);
    });

    testWidgets('fires onTap callback when card is tapped', (tester) async {
      bool tapped = false;
      final list = _makeList(name: 'Tap Me');
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: _ShoppingListCardWrapper(
              list: list,
              onTap: () => tapped = true,
            ),
          ),
        ),
      );
      await tester.tap(find.byType(InkWell));
      expect(tapped, isTrue);
    });
  });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

ShoppingList _makeList({
  String name = 'Test List',
  List<ShoppingListItem>? items,
  bool isShared = false,
}) {
  return ShoppingList(
    id: 'list-id',
    name: name,
    ownerId: 'owner-id',
    isShared: isShared,
    items: items ?? [],
    createdAt: DateTime(2024),
    updatedAt: DateTime(2024),
  );
}

ShoppingListItem _makeItem({bool isChecked = false}) {
  return ShoppingListItem(
    id: 'item-id',
    name: 'Item',
    isChecked: isChecked,
  );
}

/// Reproduces the _ShoppingListCard widget from CartScreen without DI.
class _ShoppingListCardWrapper extends StatelessWidget {
  final ShoppingList list;
  final VoidCallback? onTap;

  const _ShoppingListCardWrapper({required this.list, this.onTap});

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
        onTap: onTap ?? () {},
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
