import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/pantry/models/pantry_ingredient.dart';
import 'package:palateful/features/pantry/widgets/pantry_ingredient_tile.dart';

PantryIngredient _item({
  String name = 'Flour',
  double qty = 2,
  String unit = 'cups',
  DateTime? expiresAt,
}) {
  return PantryIngredient(
    pantryId: 'p1',
    ingredientId: 'i1',
    ingredientName: name,
    quantityDisplay: qty,
    unitDisplay: unit,
    quantityNormalized: qty,
    unitNormalized: unit,
    expiresAt: expiresAt,
    createdAt: DateTime(2026, 4, 16),
    updatedAt: DateTime(2026, 4, 16),
  );
}

void main() {
  testWidgets('renders ingredient name, quantity, and no-expiry label',
      (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: PantryIngredientTile(item: _item())),
      ),
    );

    expect(find.text('Flour'), findsOneWidget);
    expect(find.text('2 cups'), findsOneWidget);
    expect(find.text('No expiry set'), findsOneWidget);
  });

  testWidgets('tap invokes the onTap callback', (tester) async {
    var taps = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: PantryIngredientTile(item: _item(), onTap: () => taps++),
        ),
      ),
    );

    await tester.tap(find.text('Flour'));
    expect(taps, 1);
  });

  testWidgets('no "Use me up" button when onUseMeUp is null', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: PantryIngredientTile(item: _item())),
      ),
    );
    expect(find.text('Use me up'), findsNothing);
  });

  testWidgets('renders "Use me up" button when callback provided',
      (tester) async {
    var taps = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: PantryIngredientTile(
            item: _item(),
            onUseMeUp: () => taps++,
          ),
        ),
      ),
    );
    expect(find.text('Use me up'), findsOneWidget);
    await tester.tap(find.text('Use me up'));
    expect(taps, 1);
  });
}
