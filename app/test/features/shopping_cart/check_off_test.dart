import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/shopping_cart/models/shopping_list_item.dart';
import 'package:palateful/features/shopping_cart/widgets/shopping_list_item_tile.dart';

/// Widget tests for the check-off feature.
/// Tests visual states of ShoppingListItemTile and the optimistic update
/// logic for the check/uncheck flow — without DI or real network.
void main() {
  group('ShoppingListItemTile — checked state rendering', () {
    testWidgets('unchecked item renders without strikethrough', (tester) async {
      final item = ShoppingListItem(id: 'i1', name: 'Milk', isChecked: false);

      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: ShoppingListItemTile(item: item),
        ),
      ));

      final text = tester.widget<Text>(find.text('Milk'));
      expect(text.style?.decoration, isNot(TextDecoration.lineThrough));
    });

    testWidgets('checked item renders with strikethrough text', (tester) async {
      final item = ShoppingListItem(id: 'i1', name: 'Milk', isChecked: true);

      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: ShoppingListItemTile(item: item),
        ),
      ));

      final text = tester.widget<Text>(find.text('Milk'));
      expect(text.style?.decoration, TextDecoration.lineThrough);
    });

    testWidgets('checked item renders checkbox with check icon', (tester) async {
      final item = ShoppingListItem(id: 'i1', name: 'Eggs', isChecked: true);

      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: ShoppingListItemTile(item: item),
        ),
      ));

      expect(find.byIcon(Icons.check), findsOneWidget);
    });

    testWidgets('unchecked item renders checkbox without check icon',
        (tester) async {
      final item = ShoppingListItem(id: 'i1', name: 'Eggs', isChecked: false);

      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: ShoppingListItemTile(item: item),
        ),
      ));

      expect(find.byIcon(Icons.check), findsNothing);
    });
  });

  group('ShoppingListItemTile — onChecked callback', () {
    testWidgets('tapping tile triggers onChecked callback', (tester) async {
      bool? callbackValue;
      final item = ShoppingListItem(id: 'i1', name: 'Bread', isChecked: false);

      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: ShoppingListItemTile(
            item: item,
            onChecked: (v) => callbackValue = v,
          ),
        ),
      ));

      await tester.tap(find.byType(ShoppingListItemTile));
      await tester.pump();

      expect(callbackValue, isTrue);
    });

    testWidgets('tapping a checked tile passes false to onChecked',
        (tester) async {
      bool? callbackValue;
      final item = ShoppingListItem(id: 'i1', name: 'Butter', isChecked: true);

      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: ShoppingListItemTile(
            item: item,
            onChecked: (v) => callbackValue = v,
          ),
        ),
      ));

      await tester.tap(find.byType(ShoppingListItemTile));
      await tester.pump();

      expect(callbackValue, isFalse);
    });
  });

  group('Check-off optimistic update logic', () {
    testWidgets('optimistic update flips checked state immediately',
        (tester) async {
      // Use a Completer to gate the "server response" so we can verify the
      // UI shows the optimistic state BEFORE the server confirms.
      final serverCompleter = Completer<void>();
      final item = ShoppingListItem(id: 'i1', name: 'Sugar', isChecked: false);

      await tester.pumpWidget(MaterialApp(
        home: _CheckOffTester(item: item, serverCompleter: serverCompleter),
      ));

      // Initially unchecked — no strikethrough
      final textBefore = tester.widget<Text>(find.text('Sugar'));
      expect(textBefore.style?.decoration, isNot(TextDecoration.lineThrough));

      // Tap: optimistic setState fires synchronously; async function suspends at
      // `await serverCompleter.future` before the server-confirmation setState.
      await tester.tap(find.text('Check'));
      await tester.pump(); // processes optimistic setState only

      // Item should already appear checked (true optimistic — server not yet done)
      final textAfter = tester.widget<Text>(find.text('Sugar'));
      expect(textAfter.style?.decoration, TextDecoration.lineThrough);

      // Let server respond and clean up
      serverCompleter.complete();
      await tester.pumpAndSettle();
    });

    testWidgets('rollback restores item on server error', (tester) async {
      final item = ShoppingListItem(id: 'i1', name: 'Salt', isChecked: false);

      await tester.pumpWidget(MaterialApp(
        home: _CheckOffTester(item: item, throwError: true),
      ));

      // Tap to trigger check with error
      await tester.tap(find.text('Check'));
      await tester.pump(); // optimistic update fires
      await tester.pump(); // async error resolves

      // After rollback, item should be unchecked again
      final text = tester.widget<Text>(find.text('Salt'));
      expect(text.style?.decoration, isNot(TextDecoration.lineThrough));
    });

    testWidgets('error snackbar shown after rollback', (tester) async {
      final item = ShoppingListItem(id: 'i1', name: 'Pepper', isChecked: false);

      await tester.pumpWidget(MaterialApp(
        home: _CheckOffTester(item: item, throwError: true),
      ));

      await tester.tap(find.text('Check'));
      await tester.pump(); // optimistic update
      await tester.pump(); // error resolves
      await tester.pump(); // snackbar renders

      expect(find.text('Failed to update item'), findsOneWidget);
    });
  });
}

// ---------------------------------------------------------------------------
// Test widget — simulates _toggleItemChecked optimistic logic without DI
// ---------------------------------------------------------------------------

class _CheckOffTester extends StatefulWidget {
  final ShoppingListItem item;
  final bool throwError;
  /// When provided, the "server response" is gated behind this completer,
  /// allowing tests to verify the optimistic interim state before completion.
  final Completer<void>? serverCompleter;

  const _CheckOffTester({
    required this.item,
    this.throwError = false,
    this.serverCompleter,
  });

  @override
  State<_CheckOffTester> createState() => _CheckOffTesterState();
}

class _CheckOffTesterState extends State<_CheckOffTester> {
  late ShoppingListItem _item;

  @override
  void initState() {
    super.initState();
    _item = widget.item;
  }

  void _handleItemUpdated(ShoppingListItem updated) {
    setState(() {
      _item = updated;
    });
  }

  Future<void> _toggleItemChecked() async {
    // Optimistic update — matches the production pattern
    final original = _item;
    final optimistic = _item.copyWith(isChecked: !_item.isChecked);
    _handleItemUpdated(optimistic);
    try {
      if (widget.throwError) throw Exception('network error');
      // Simulate async server round-trip (gated by completer when provided)
      if (widget.serverCompleter != null) {
        await widget.serverCompleter!.future;
      }
      final updated = original.copyWith(isChecked: !original.isChecked);
      _handleItemUpdated(updated);
    } catch (_) {
      // Rollback
      _handleItemUpdated(original);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to update item')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          ShoppingListItemTile(item: _item),
          ElevatedButton(
            onPressed: _toggleItemChecked,
            child: const Text('Check'),
          ),
        ],
      ),
    );
  }
}
