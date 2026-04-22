// rp-5 AC #4 — end-to-end copy sweep. Exercises one representative
// mutation per feature through `showMutationFailureSnackbar` and
// asserts the rendered Snackbar copy matches the expected
// `"Couldn't <verb> <noun>"` pattern.
//
// This is the cross-epic smoke test that catches copy regressions
// without requiring a full service-layer fake per feature.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/state/mutation_failure_copy.dart';
import 'package:palateful/core/state/mutation_snackbar.dart';

Future<void> _pumpAndTrigger(
  WidgetTester tester,
  MutationType type,
) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: Builder(
          builder: (ctx) => Center(
            child: ElevatedButton(
              onPressed: () => showMutationFailureSnackbar(
                ctx,
                type,
                () {},
              ),
              child: const Text('Trigger'),
            ),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('Trigger'));
  await tester.pump();
}

void main() {
  group('end-to-end: one mutation per feature renders central Snackbar', () {
    const representatives = <MutationType>[
      MutationType.createRecipe, // recipes feature
      MutationType.updateRecipeBook, // recipe-books
      MutationType.updateNotificationPrefs, // profile/prefs
      MutationType.addPantryItem, // pantry
      MutationType.createCookingLog, // cooking log (rp-3 handoff)
      MutationType.addShoppingListItem, // shopping cart
      MutationType.dismissImportItem, // imports (foundation)
      // rmc-5 representatives — one per calendar / meal-event / recurrence verb.
      MutationType.createCalendar,
      MutationType.deleteCalendar,
      MutationType.createMealEvent,
      MutationType.planMealEvent,
      MutationType.markMealCompleted,
      MutationType.rescheduleMealEvent,
      MutationType.createRecurrenceRule,
    ];

    for (final type in representatives) {
      testWidgets('${type.name} → central Snackbar with expected copy',
          (tester) async {
        await _pumpAndTrigger(tester, type);
        final copy = mutationFailureCopy[type]!;
        expect(find.text(copy.title), findsOneWidget);
        expect(find.text('Retry'), findsOneWidget);
      });
    }
  });

  // rmc-5 AC #6 — the copy map must have an entry for every enum value.
  // CI fails the moment a new MutationType lands without `Couldn't <verb>
  // <noun>` copy. Avoids the silent "Couldn't complete that action"
  // fallback shipping to production.
  test('every MutationType has a mutationFailureCopy entry', () {
    final missing = MutationType.values
        .where((t) => mutationFailureCopy[t] == null)
        .map((t) => t.name)
        .toList();
    expect(missing, isEmpty,
        reason: 'Missing mutationFailureCopy entries: $missing');
  });
}
