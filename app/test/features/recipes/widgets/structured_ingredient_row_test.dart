import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:palateful/features/recipes/widgets/structured_ingredient_row.dart';

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
        ),
      ));
      expect(find.widgetWithText(TextField, '1/2'), findsOneWidget);
      expect(find.widgetWithText(TextField, 'butter'), findsOneWidget);
      expect(find.widgetWithText(TextField, 'melted'), findsOneWidget);
    });

    testWidgets('renders empty row with placeholders', (tester) async {
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(),
          onChanged: (_) {},
        ),
      ));
      final qty = tester
          .widget<TextField>(find.byKey(const Key('ingredient_row_qty')));
      expect(qty.decoration?.hintText, 'Qty');
      final name = tester
          .widget<TextField>(find.byKey(const Key('ingredient_row_name')));
      expect(name.decoration?.hintText, 'Name');
      final notes = tester
          .widget<TextField>(find.byKey(const Key('ingredient_row_notes')));
      expect(notes.decoration?.hintText?.startsWith('Notes'), isTrue);
    });

    testWidgets('renders legacy ingredient — name only', (tester) async {
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(name: 'all-purpose flour'),
          onChanged: (_) {},
        ),
      ));
      expect(find.widgetWithText(TextField, 'all-purpose flour'),
          findsOneWidget);
      expect(find.widgetWithText(TextField, ''), findsWidgets);
    });

    testWidgets('editing name fires onChanged with new value', (tester) async {
      IngredientRowData? latest;
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(name: 'butter'),
          onChanged: (v) => latest = v,
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
        ),
      ));
      await tester.enterText(
          find.byKey(const Key('ingredient_row_qty')), '1 1/2');
      await tester.pump();
      expect(latest?.quantity, 1.5);
    });

    testWidgets('editing notes fires onChanged', (tester) async {
      IngredientRowData? latest;
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(name: 'butter'),
          onChanged: (v) => latest = v,
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
        ),
      ));
      final qtyFinder = find.byKey(const Key('ingredient_row_qty'));
      await tester.tap(qtyFinder);
      await tester.pumpAndSettle();
      await tester.enterText(qtyFinder, '0.5');
      // Simulate blur: tap somewhere else.
      await tester.tap(find.byKey(const Key('ingredient_row_name')));
      await tester.pumpAndSettle();
      expect(find.widgetWithText(TextField, '1/2'), findsOneWidget);
    });

    testWidgets('optional toggle emits isOptional=true', (tester) async {
      IngredientRowData? latest;
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(name: 'butter'),
          onChanged: (v) => latest = v,
        ),
      ));
      await tester.tap(find.byKey(const Key('ingredient_row_optional')));
      await tester.pump();
      expect(latest?.isOptional, isTrue);
    });

    testWidgets('optional toggle has row-specific Semantics label',
        (tester) async {
      final handle = tester.ensureSemantics();
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(name: 'butter'),
          onChanged: (_) {},
        ),
      ));
      expect(
        find.bySemanticsLabel(RegExp(r'Mark butter as optional')),
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
        ),
        width: 320,
      ));
      // If overflow occurred, the framework would log a render exception
      // captured by tester.takeException().
      expect(tester.takeException(), isNull);
    });
  });
}
