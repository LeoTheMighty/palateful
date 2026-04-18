import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:palateful/core/constants/ingredient_units.dart';
import 'package:palateful/features/recipes/services/session_alias_map.dart';
import 'package:palateful/features/recipes/widgets/unit_input.dart';

SessionAliasMap _newAliasMap() =>
    SessionAliasMap.withFetcher(() async => null);

Widget _wrap(Widget child) {
  return MaterialApp(
    home: Scaffold(
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: SizedBox(width: 200, child: child),
      ),
    ),
  );
}

void main() {
  late SessionAliasMap aliasMap;

  setUp(() {
    aliasMap = _newAliasMap();
  });

  group('kCuratedUnits', () {
    test('contains 15 canonical units in intended order', () {
      expect(kCuratedUnits, <String>[
        'cup', 'tbsp', 'tsp', 'oz', 'fl oz', 'ml', 'l', 'g',
        'kg', 'lb', 'each', 'pinch', 'dash', 'clove', 'slice',
      ]);
    });

    test('filterCuratedUnits empty returns full list', () {
      expect(filterCuratedUnits(''), equals(kCuratedUnits));
    });

    test('filterCuratedUnits matches substring, case-insensitive', () {
      expect(filterCuratedUnits('Cup'), contains('cup'));
      expect(filterCuratedUnits('oz'), containsAll(['oz', 'fl oz']));
      expect(filterCuratedUnits('lb'), equals(['lb']));
    });

    test('filterCuratedUnits no match returns empty list', () {
      expect(filterCuratedUnits('zzz'), isEmpty);
    });
  });

  group('UnitInput', () {
    testWidgets('renders curated value in field', (tester) async {
      await tester.pumpWidget(_wrap(
        UnitInput(value: 'cup', onChanged: (_) {}, aliasMap: aliasMap),
      ));
      expect(find.widgetWithText(TextField, 'cup'), findsOneWidget);
    });

    testWidgets('renders custom value in field', (tester) async {
      await tester.pumpWidget(_wrap(
        UnitInput(value: 'stalk', onChanged: (_) {}, aliasMap: aliasMap),
      ));
      expect(find.widgetWithText(TextField, 'stalk'), findsOneWidget);
    });

    testWidgets('renders null as empty with placeholder', (tester) async {
      await tester.pumpWidget(_wrap(
        UnitInput(value: null, onChanged: (_) {}, aliasMap: aliasMap),
      ));
      final field = tester.widget<TextField>(find.byType(TextField));
      expect(field.controller?.text, isEmpty);
      expect(field.decoration?.hintText, 'Unit');
    });

    testWidgets('dropdown opens on focus and shows curated list',
        (tester) async {
      await tester.pumpWidget(_wrap(
        UnitInput(value: null, onChanged: (_) {}, aliasMap: aliasMap),
      ));
      await tester.tap(find.byType(TextField));
      await tester.pumpAndSettle();
      // Curated unit entries use Key('unit_option_<unit>').
      for (final u in kCuratedUnits.take(4)) {
        expect(find.byKey(Key('unit_option_$u')), findsOneWidget);
      }
      expect(find.text('Custom units apply to this ingredient only'),
          findsOneWidget);
    });

    testWidgets('typing filters the list', (tester) async {
      await tester.pumpWidget(_wrap(
        UnitInput(value: null, onChanged: (_) {}, aliasMap: aliasMap),
      ));
      await tester.tap(find.byType(TextField));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), 'oz');
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('unit_option_oz')), findsOneWidget);
      expect(find.byKey(const Key('unit_option_fl oz')), findsOneWidget);
      expect(find.byKey(const Key('unit_option_cup')), findsNothing);
    });

    testWidgets('selecting curated unit fires onChanged with canonical form',
        (tester) async {
      String? selected = 'SENTINEL';
      await tester.pumpWidget(_wrap(
        UnitInput(
            value: null,
            onChanged: (v) => selected = v,
            aliasMap: aliasMap),
      ));
      await tester.tap(find.byType(TextField));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('unit_option_tbsp')));
      await tester.pumpAndSettle();
      expect(selected, 'tbsp');
    });

    testWidgets('typing unknown unit surfaces "Add custom" entry', (tester) async {
      String? selected = 'SENTINEL';
      await tester.pumpWidget(_wrap(
        UnitInput(
            value: null,
            onChanged: (v) => selected = v,
            aliasMap: aliasMap),
      ));
      await tester.tap(find.byType(TextField));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), 'stalk');
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('unit_add_custom')), findsOneWidget);
      expect(find.text('Add custom: "stalk"'), findsOneWidget);

      await tester.tap(find.byKey(const Key('unit_add_custom')));
      await tester.pumpAndSettle();
      expect(selected, 'stalk');
    });

    testWidgets('typing an exact curated match hides "Add custom"',
        (tester) async {
      await tester.pumpWidget(_wrap(
        UnitInput(value: null, onChanged: (_) {}, aliasMap: aliasMap),
      ));
      await tester.tap(find.byType(TextField));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), 'tbsp');
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('unit_add_custom')), findsNothing);
    });

    testWidgets('semantic label applied', (tester) async {
      await tester.pumpWidget(_wrap(
        UnitInput(value: null, onChanged: (_) {}, aliasMap: aliasMap),
      ));
      expect(
        find.bySemanticsLabel('Unit selector'),
        findsAtLeastNWidgets(1),
      );
    });

    testWidgets('parent sync: external value change updates field',
        (tester) async {
      String value = 'cup';
      await tester.pumpWidget(_wrap(
        StatefulBuilder(
          builder: (ctx, setState) => Column(
            children: [
              UnitInput(
                  value: value, onChanged: (_) {}, aliasMap: aliasMap),
              ElevatedButton(
                onPressed: () => setState(() => value = 'g'),
                child: const Text('change'),
              ),
            ],
          ),
        ),
      ));
      expect(find.widgetWithText(TextField, 'cup'), findsOneWidget);
      await tester.tap(find.text('change'));
      await tester.pump();
      expect(find.widgetWithText(TextField, 'g'), findsOneWidget);
    });
  });

  group('UnitInput coerce-on-blur (riip-5)', () {
    testWidgets('typing "tablespoon" + blur snaps to "tbsp" with cursor at end',
        (tester) async {
      String? out = 'SENTINEL';
      await tester.pumpWidget(_wrap(
        UnitInput(
            value: null,
            onChanged: (v) => out = v,
            aliasMap: aliasMap),
      ));
      await tester.tap(find.byType(TextField));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), 'tablespoon');
      // Blur by tapping outside.
      await tester.tap(find.byType(Scaffold));
      await tester.pumpAndSettle();
      expect(out, 'tbsp');
      final field = tester.widget<TextField>(find.byType(TextField));
      expect(field.controller!.text, 'tbsp');
      expect(field.controller!.selection.baseOffset, 'tbsp'.length);
    });

    testWidgets('typing "Tbsp." + blur strips punctuation + lowercases to "tbsp"',
        (tester) async {
      String? out;
      await tester.pumpWidget(_wrap(
        UnitInput(
            value: null,
            onChanged: (v) => out = v,
            aliasMap: aliasMap),
      ));
      await tester.tap(find.byType(TextField));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), 'Tbsp.');
      await tester.tap(find.byType(Scaffold));
      await tester.pumpAndSettle();
      expect(out, 'tbsp');
    });

    testWidgets('typing "weirdunit" + blur returns the normalized input',
        (tester) async {
      String? out;
      await tester.pumpWidget(_wrap(
        UnitInput(
            value: null,
            onChanged: (v) => out = v,
            aliasMap: aliasMap),
      ));
      await tester.tap(find.byType(TextField));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), 'weirdunit');
      await tester.tap(find.byType(Scaffold));
      await tester.pumpAndSettle();
      expect(out, 'weirdunit');
    });

    testWidgets('typing "tablespoon " (trailing space) coerces immediately',
        (tester) async {
      String? out;
      await tester.pumpWidget(_wrap(
        UnitInput(
            value: null,
            onChanged: (v) => out = v,
            aliasMap: aliasMap),
      ));
      await tester.tap(find.byType(TextField));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), 'tablespoon ');
      await tester.pump();
      expect(out, 'tbsp');
      final field = tester.widget<TextField>(find.byType(TextField));
      expect(field.controller!.text, 'tbsp');
    });
  });

  group('SessionAliasMap.coerce', () {
    test('passes through canonical input unchanged', () {
      final map = _newAliasMap();
      expect(map.coerce('tbsp'), 'tbsp');
      expect(map.coerce('cup'), 'cup');
    });

    test('hits hardcoded fallback alias on miss-of-canonical', () {
      final map = _newAliasMap();
      expect(map.coerce('tablespoon'), 'tbsp');
      expect(map.coerce('TEASPOONS'), 'tsp');
      expect(map.coerce('Grams.'), 'g');
    });

    test('returns trimmed/lowercased input on full miss', () {
      final map = _newAliasMap();
      expect(map.coerce('  Weirdunit. '), 'weirdunit');
    });

    test('null and empty pass through without normalization', () {
      final map = _newAliasMap();
      expect(map.coerce(null), isNull);
      expect(map.coerce(''), '');
      expect(map.coerce('   '), '   ');
    });
  });
}
