import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/pantry/screens/pantry_editor_screen.dart';

void main() {
  group('PantryEditorScreen in add mode', () {
    testWidgets('renders free-text ingredient name field (no server search)',
        (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: PantryEditorScreen(ingredientId: 'new'),
        ),
      );
      expect(find.byKey(const Key('pantry_editor_name')), findsOneWidget);
      expect(find.text('Search ingredients'), findsNothing);
      expect(find.text('Save'), findsOneWidget);
    });

    testWidgets('save is disabled until name + quantity are filled',
        (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: PantryEditorScreen(ingredientId: 'new'),
        ),
      );
      final save = tester.widget<FilledButton>(find.byType(FilledButton));
      expect(save.onPressed, isNull);
    });

    testWidgets('app bar shows add-mode title', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: PantryEditorScreen(ingredientId: 'new'),
        ),
      );
      expect(find.text('Add pantry item'), findsOneWidget);
    });
  });

  group('PantryEditorScreen in edit mode', () {
    testWidgets('app bar shows edit-mode title + delete icon', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: PantryEditorScreen(ingredientId: 'some-existing-id'),
        ),
      );
      expect(find.text('Edit pantry item'), findsOneWidget);
      expect(find.byIcon(Icons.delete_outline), findsOneWidget);
    });
  });
}
