import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/pantry/screens/pantry_editor_screen.dart';

void main() {
  group('PantryEditorScreen in add mode', () {
    testWidgets('renders ingredient search first', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: PantryEditorScreen(ingredientId: 'new'),
        ),
      );
      // The search text field is shown first when no ingredient is picked.
      expect(find.text('Search ingredients'), findsOneWidget);
      expect(find.text('Save'), findsNothing);
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
