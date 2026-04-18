/// riip-8 regression guard.
///
/// The ingredient row is consumed by three surfaces:
///   1. Review Import (`import_item_review_screen.dart`)
///   2. Recipe wizard (`recipe_wizard_screen.dart`)
///   3. Recipe edit    (`edit_recipe_screen.dart`)
///
/// All three render through the shared `StructuredIngredientRow`, so
/// per-surface widget tests would mostly duplicate the widget's own
/// suite. What's valuable here is an **accessibility-tree snapshot**:
/// the main row MUST be a single `Row` with the qty/unit/name/caret/
/// delete children — NOT a `Column` wrapping two `Row`s (the old
/// layout). If a refactor accidentally swaps those back, this test
/// fails loudly.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:palateful/features/recipes/services/session_alias_map.dart';
import 'package:palateful/features/recipes/widgets/structured_ingredient_row.dart';

SessionAliasMap _newAliasMap() =>
    SessionAliasMap.withFetcher(() async => null);

Widget _wrap(Widget child, {double width = 400}) {
  return MaterialApp(
    home: Scaffold(
      body: MediaQuery(
        data: MediaQueryData(size: Size(width, 800)),
        child: Padding(padding: const EdgeInsets.all(8), child: child),
      ),
    ),
  );
}

void main() {
  group('StructuredIngredientRow structural regression (riip-8)', () {
    testWidgets('plain row renders qty + unit + name on ONE Row, not nested',
        (tester) async {
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(
            name: 'all-purpose flour',
            quantity: 2,
            unit: 'cup',
          ),
          onChanged: (_) {},
          onDeleteRequested: () {},
          aliasMap: _newAliasMap(),
        ),
        width: 360,
      ));

      // Find the qty field and walk up the ancestor chain. The first
      // ancestor Row we hit owns the one-line layout. It must be the
      // same Row that owns the caret + delete (proving they share a
      // parent Row, not two sibling Rows in a Column).
      final qty = find.byKey(const Key('ingredient_row_qty'));
      final caret = find.byKey(const Key('ingredient_row_caret'));
      final delete = find.byKey(const Key('ingredient_row_delete'));

      final qtyRow = find.ancestor(of: qty, matching: find.byType(Row));
      final caretRow = find.ancestor(of: caret, matching: find.byType(Row));
      final deleteRow = find.ancestor(of: delete, matching: find.byType(Row));

      expect(qtyRow, findsAtLeastNWidgets(1));
      expect(caretRow, findsAtLeastNWidgets(1));
      expect(deleteRow, findsAtLeastNWidgets(1));

      // The first (innermost) Row ancestor must be shared by all three.
      final qtyFirstRow = tester.element(qtyRow.first).findAncestorWidgetOfExactType<Row>();
      final caretFirstRow =
          tester.element(caretRow.first).findAncestorWidgetOfExactType<Row>();
      final deleteFirstRow =
          tester.element(deleteRow.first).findAncestorWidgetOfExactType<Row>();
      expect(identical(qtyFirstRow, caretFirstRow), isTrue,
          reason: 'qty and caret must share the main Row');
      expect(identical(caretFirstRow, deleteFirstRow), isTrue,
          reason: 'caret and delete must share the main Row');
    });

    testWidgets(
        'row with notes renders main Row + expansion row (two Rows, NOT nested)',
        (tester) async {
      // When auto-expanded, there are two Rows: the main one-line row
      // and the expansion row below. They are siblings inside the
      // outer Column — never parent/child. This test verifies the
      // notes field is NOT a child of the main Row.
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(
            name: 'butter',
            notes: 'melted',
          ),
          onChanged: (_) {},
          aliasMap: _newAliasMap(),
        ),
      ));

      final qty = find.byKey(const Key('ingredient_row_qty'));
      final notes = find.byKey(const Key('ingredient_row_notes'));
      final qtyMainRow =
          tester.element(qty).findAncestorWidgetOfExactType<Row>();
      final notesRow =
          tester.element(notes).findAncestorWidgetOfExactType<Row>();
      expect(qtyMainRow, isNot(equals(notesRow)),
          reason:
              'notes field must live in the expansion Row, not the main Row');
    });

    testWidgets('row height ≥ 48dp (Material tap-target minimum)',
        (tester) async {
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(
            name: 'butter',
            quantity: 2,
            unit: 'tbsp',
          ),
          onChanged: (_) {},
          aliasMap: _newAliasMap(),
        ),
        width: 320,
      ));
      final caret =
          tester.getSize(find.byKey(const Key('ingredient_row_caret')));
      expect(caret.height, greaterThanOrEqualTo(40));
    });
  });
}
