import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:palateful/features/recipes/services/session_alias_map.dart';
import 'package:palateful/features/recipes/widgets/ingredient_row_state_badge.dart';
import 'package:palateful/features/recipes/widgets/structured_ingredient_row.dart';

SessionAliasMap _newAliasMap() =>
    SessionAliasMap.withFetcher(() async => null);

Widget _wrap(Widget child) {
  return MaterialApp(
    home: Scaffold(body: Padding(padding: const EdgeInsets.all(8), child: child)),
  );
}

void main() {
  group('IngredientRowStateBadge', () {
    testWidgets('not rendered when pendingReviewIngredient is false',
        (tester) async {
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(
            name: 'butter',
            pendingReviewIngredient: false,
          ),
          onChanged: (_) {},
          aliasMap: _newAliasMap(),
        ),
      ));
      expect(find.byKey(const Key('ingredient_row_state_badge')), findsNothing);
    });

    testWidgets('rendered when pendingReviewIngredient is true',
        (tester) async {
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(
            name: 'butter',
            pendingReviewIngredient: true,
          ),
          onChanged: (_) {},
          aliasMap: _newAliasMap(),
        ),
      ));
      expect(find.byKey(const Key('ingredient_row_state_badge')), findsOneWidget);
      expect(find.byIcon(Icons.auto_awesome), findsOneWidget);
    });

    testWidgets('tapping the badge opens a bottom-sheet explainer',
        (tester) async {
      await tester.pumpWidget(_wrap(
        StructuredIngredientRow(
          value: const IngredientRowData(
            name: 'butter',
            pendingReviewIngredient: true,
          ),
          onChanged: (_) {},
          aliasMap: _newAliasMap(),
        ),
      ));
      await tester.tap(find.byKey(const Key('ingredient_row_state_badge')));
      await tester.pumpAndSettle();
      expect(find.text('New ingredient'), findsOneWidget);
      // Copy includes the ingredient name in quotes.
      expect(find.textContaining("'butter'"), findsOneWidget);
      // Dismiss.
      await tester.tap(find.byKey(const Key('ingredient_row_state_badge_dismiss')));
      await tester.pumpAndSettle();
      expect(find.text('New ingredient'), findsNothing);
    });

    testWidgets('unnamed ingredient falls back to "This ingredient"',
        (tester) async {
      await tester.pumpWidget(_wrap(
        const IngredientRowStateBadge(ingredientName: null),
      ));
      await tester.tap(find.byKey(const Key('ingredient_row_state_badge')));
      await tester.pumpAndSettle();
      expect(find.textContaining('This ingredient'), findsOneWidget);
    });

    testWidgets('semantic label marks the badge as a button', (tester) async {
      final handle = tester.ensureSemantics();
      await tester.pumpWidget(_wrap(
        const IngredientRowStateBadge(ingredientName: 'butter'),
      ));
      expect(
        find.bySemanticsLabel('New ingredient — tap for details'),
        findsAtLeastNWidgets(1),
      );
      handle.dispose();
    });
  });
}
