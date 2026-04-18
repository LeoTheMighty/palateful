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
        child: Padding(
          padding: const EdgeInsets.all(8),
          child: child,
        ),
      ),
    ),
  );
}

void main() {
  late SessionAliasMap aliasMap;

  setUp(() {
    aliasMap = _newAliasMap();
  });

  group('IngredientRowData', () {
    test('copyWith distinguishes explicit null from absent', () {
      const v = IngredientRowData(
        name: 'butter',
        quantity: 0.5,
        unit: 'cup',
        notes: 'melted',
        isOptional: true,
      );
      // Default copy preserves all fields.
      expect(v.copyWith().name, 'butter');
      expect(v.copyWith().quantity, 0.5);
      // Explicit null clears the field.
      expect(v.copyWith(name: null).name, isNull);
      expect(v.copyWith(quantity: null).quantity, isNull);
      // Flag can be toggled.
      expect(v.copyWith(isOptional: false).isOptional, isFalse);
    });

    test('expanded auto-defaults to true when notes present', () {
      const v = IngredientRowData(name: 'butter', notes: 'melted');
      expect(v.expanded, isTrue);
      expect(v.hasHiddenContent, isFalse);
    });

    test('expanded auto-defaults to true when isOptional', () {
      const v = IngredientRowData(name: 'butter', isOptional: true);
      expect(v.expanded, isTrue);
    });

    test('expanded false by default for plain row', () {
      const v = IngredientRowData(name: 'salt');
      expect(v.expanded, isFalse);
      expect(v.hasHiddenContent, isFalse);
    });

    test('manual collapse persists via copyWith(expanded: false)', () {
      const v = IngredientRowData(name: 'butter', notes: 'melted');
      final collapsed = v.copyWith(expanded: false);
      expect(collapsed.expanded, isFalse);
      expect(collapsed.hasHiddenContent, isTrue);
    });
  });

  group('StructuredIngredientRow', () {
    testWidgets('renders populated row with quantity as fraction',
        (tester) async {
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(
            name: 'butter',
            quantity: 0.5,
            unit: 'cup',
            notes: 'melted',
          ),
          onChanged: (_) {},
          aliasMap: aliasMap,
        ),
      ));
      expect(find.widgetWithText(TextField, '1/2'), findsOneWidget);
      expect(find.widgetWithText(TextField, 'butter'), findsOneWidget);
      // Notes auto-expanded because notes is non-empty.
      expect(find.widgetWithText(TextField, 'melted'), findsOneWidget);
    });

    testWidgets('renders empty row with placeholders, caret collapsed',
        (tester) async {
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(),
          onChanged: (_) {},
          aliasMap: aliasMap,
        ),
      ));
      final qty = tester
          .widget<TextField>(find.byKey(const Key('ingredient_row_qty')));
      expect(qty.decoration?.hintText, 'Qty');
      final name = tester
          .widget<TextField>(find.byKey(const Key('ingredient_row_name')));
      expect(name.decoration?.hintText, 'Name');
      // Caret collapsed → notes field absent.
      expect(find.byKey(const Key('ingredient_row_notes')), findsNothing);
    });

    testWidgets('editing name fires onChanged with new value', (tester) async {
      IngredientRowData? latest;
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(name: 'butter'),
          onChanged: (v) => latest = v,
          aliasMap: aliasMap,
        ),
      ));
      await tester.enterText(
          find.byKey(const Key('ingredient_row_name')), 'margarine');
      await tester.pump();
      expect(latest?.name, 'margarine');
    });

    testWidgets('editing qty fires onChanged with parsed numeric',
        (tester) async {
      IngredientRowData? latest;
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(),
          onChanged: (v) => latest = v,
          aliasMap: aliasMap,
        ),
      ));
      await tester.enterText(
          find.byKey(const Key('ingredient_row_qty')), '1 1/2');
      await tester.pump();
      expect(latest?.quantity, 1.5);
    });

    testWidgets('editing notes (after expanding) fires onChanged',
        (tester) async {
      IngredientRowData? latest;
      // Pre-expand by passing notes (auto-expand kicks in).
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(name: 'butter', notes: ' '),
          onChanged: (v) => latest = v,
          aliasMap: aliasMap,
        ),
      ));
      await tester.enterText(
          find.byKey(const Key('ingredient_row_notes')), 'melted');
      await tester.pump();
      expect(latest?.notes, 'melted');
    });

    testWidgets('qty re-formats to fraction on blur', (tester) async {
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(),
          onChanged: (_) {},
          aliasMap: aliasMap,
        ),
      ));
      final qtyFinder = find.byKey(const Key('ingredient_row_qty'));
      await tester.tap(qtyFinder);
      await tester.pumpAndSettle();
      await tester.enterText(qtyFinder, '0.5');
      // Blur by tapping name field.
      await tester.tap(find.byKey(const Key('ingredient_row_name')));
      await tester.pumpAndSettle();
      expect(find.widgetWithText(TextField, '1/2'), findsOneWidget);
    });

    testWidgets('optional toggle (in expanded row) emits isOptional=true',
        (tester) async {
      IngredientRowData? latest;
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          // Pre-expanded so optional checkbox is reachable.
          value:
              const IngredientRowData(name: 'butter', expanded: true),
          onChanged: (v) => latest = v,
          aliasMap: aliasMap,
        ),
      ));
      await tester.tap(find.byKey(const Key('ingredient_row_optional')));
      await tester.pump();
      expect(latest?.isOptional, isTrue);
    });

    testWidgets('row Semantics carries name and notes', (tester) async {
      final handle = tester.ensureSemantics();
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(
            name: 'butter',
            quantity: 2,
            unit: 'tbsp',
            notes: 'melted',
            isOptional: true,
          ),
          onChanged: (_) {},
          aliasMap: aliasMap,
        ),
      ));
      expect(
        find.bySemanticsLabel(RegExp(r'Ingredient 2 tbsp butter')),
        findsAtLeastNWidgets(1),
      );
      expect(
        find.bySemanticsLabel(RegExp(r'optional, notes: melted')),
        findsAtLeastNWidgets(1),
      );
      handle.dispose();
    });

    testWidgets('delete callback fires when trash tapped', (tester) async {
      var deleted = false;
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(name: 'butter'),
          onChanged: (_) {},
          onDeleteRequested: () => deleted = true,
          aliasMap: aliasMap,
        ),
      ));
      await tester.tap(find.byKey(const Key('ingredient_row_delete')));
      await tester.pump();
      expect(deleted, isTrue);
    });

    testWidgets('delete icon hidden when no callback provided', (tester) async {
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(name: 'butter'),
          onChanged: (_) {},
          aliasMap: aliasMap,
        ),
      ));
      expect(find.byKey(const Key('ingredient_row_delete')), findsNothing);
    });

    testWidgets('quantity input accepts only digits, dot, slash, space',
        (tester) async {
      IngredientRowData? latest;
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(),
          onChanged: (v) => latest = v,
          aliasMap: aliasMap,
        ),
      ));
      await tester.enterText(
          find.byKey(const Key('ingredient_row_qty')), '1a2b3');
      await tester.pump();
      // Letters filtered out; parse of "123" → 123.
      expect(latest?.quantity, 123);
    });

    testWidgets('parent value sync updates fields when not focused',
        (tester) async {
      IngredientRowData value =
          const IngredientRowData(name: 'butter', quantity: 0.5);
      await tester.pumpWidget(_wrap(
        StatefulBuilder(
          builder: (ctx, setState) => Column(
            children: [
              StructuredIngredientRow(
                value: value,
                onChanged: (v) => setState(() => value = v),
                aliasMap: aliasMap,
              ),
              ElevatedButton(
                onPressed: () => setState(() => value = const IngredientRowData(
                      name: 'flour',
                      quantity: 2,
                    )),
                child: const Text('replace'),
              ),
            ],
          ),
        ),
      ));
      expect(find.widgetWithText(TextField, '1/2'), findsOneWidget);
      expect(find.widgetWithText(TextField, 'butter'), findsOneWidget);
      await tester.tap(find.text('replace'));
      await tester.pump();
      expect(find.widgetWithText(TextField, '2'), findsOneWidget);
      expect(find.widgetWithText(TextField, 'flour'), findsOneWidget);
    });

    testWidgets('fits iPhone SE 1st-gen width (320px) without overflow',
        (tester) async {
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(
            name: 'all-purpose flour',
            quantity: 2.5,
            unit: 'cup',
            notes: 'sifted, spooned into measuring cup',
          ),
          onChanged: (_) {},
          onDeleteRequested: () {},
          aliasMap: aliasMap,
        ),
        width: 320,
      ));
      // If overflow occurred, the framework would log a render exception
      // captured by tester.takeException().
      expect(tester.takeException(), isNull);
    });
  });

  group('StructuredIngredientRow caret + expansion (riip-6)', () {
    testWidgets('caret collapsed by default for plain row', (tester) async {
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(name: 'salt'),
          onChanged: (_) {},
          aliasMap: aliasMap,
        ),
      ));
      // Notes field hidden.
      expect(find.byKey(const Key('ingredient_row_notes')), findsNothing);
      // No dot when there's no hidden content.
      expect(find.byKey(const Key('ingredient_row_caret_dot')), findsNothing);
    });

    testWidgets('initial notes auto-expands the caret', (tester) async {
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(
            name: 'butter',
            notes: 'melted',
          ),
          onChanged: (_) {},
          aliasMap: aliasMap,
        ),
      ));
      expect(find.byKey(const Key('ingredient_row_notes')), findsOneWidget);
    });

    testWidgets('initial isOptional=true auto-expands the caret',
        (tester) async {
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(
            name: 'butter',
            isOptional: true,
          ),
          onChanged: (_) {},
          aliasMap: aliasMap,
        ),
      ));
      expect(find.byKey(const Key('ingredient_row_optional')), findsOneWidget);
    });

    testWidgets('manual collapse with hidden content shows the dot',
        (tester) async {
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(
            name: 'butter',
            notes: 'melted',
            expanded: false,
          ),
          onChanged: (_) {},
          aliasMap: aliasMap,
        ),
      ));
      expect(find.byKey(const Key('ingredient_row_caret_dot')), findsOneWidget);
    });

    testWidgets('tapping caret toggles expansion via onChanged', (tester) async {
      IngredientRowData value = const IngredientRowData(name: 'salt');
      await tester.pumpWidget(_wrap(
        StatefulBuilder(
          builder: (ctx, setState) => StructuredIngredientRow(
            value: value,
            onChanged: (v) => setState(() => value = v),
            aliasMap: aliasMap,
          ),
        ),
      ));
      // Collapsed initially.
      expect(find.byKey(const Key('ingredient_row_notes')), findsNothing);
      await tester.tap(find.byKey(const Key('ingredient_row_caret')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('ingredient_row_notes')), findsOneWidget);
    });

    testWidgets('manual collapse survives parent rebuild', (tester) async {
      // Parent owns the value; collapse via onChanged then trigger a
      // parent rebuild without touching the value. State is preserved
      // because expansion lives on IngredientRowData.
      IngredientRowData value =
          const IngredientRowData(name: 'butter', notes: 'melted');
      await tester.pumpWidget(_wrap(
        StatefulBuilder(
          builder: (ctx, setState) => Column(
            children: [
              StructuredIngredientRow(
                value: value,
                onChanged: (v) => setState(() => value = v),
                aliasMap: aliasMap,
              ),
              ElevatedButton(
                onPressed: () => setState(() {}),
                child: const Text('rebuild'),
              ),
            ],
          ),
        ),
      ));
      // Auto-expanded.
      expect(find.byKey(const Key('ingredient_row_notes')), findsOneWidget);
      // Collapse.
      await tester.tap(find.byKey(const Key('ingredient_row_caret')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('ingredient_row_notes')), findsNothing);
      // Rebuild parent — collapse must survive.
      await tester.tap(find.text('rebuild'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('ingredient_row_notes')), findsNothing);
      // And the dot is still there because there is hidden content.
      expect(find.byKey(const Key('ingredient_row_caret_dot')), findsOneWidget);
    });

    testWidgets(
        'locked widths at 320pt — qty 48, unit 72, caret 40, delete 40',
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
          aliasMap: aliasMap,
        ),
        width: 320,
      ));
      final qty = tester.getSize(find.byKey(const Key('ingredient_row_qty')));
      expect(qty.width, 48);
      // The UnitInput hosts a TextField — the parent SizedBox locks the
      // width via _RowLayout.unit.
      final unit = tester.getSize(find.byKey(const Key('ingredient_row_unit')));
      expect(unit.width, 72);
      final caret =
          tester.getSize(find.byKey(const Key('ingredient_row_caret')));
      expect(caret.width, lessThanOrEqualTo(40));
      expect(caret.height, lessThanOrEqualTo(40));
      final delete =
          tester.getSize(find.byKey(const Key('ingredient_row_delete')));
      expect(delete.width, lessThanOrEqualTo(40));
    });
  });
}
