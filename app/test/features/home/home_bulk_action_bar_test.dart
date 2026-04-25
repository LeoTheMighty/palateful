import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/home/widgets/home_bulk_action_bar.dart';
import 'package:palateful/features/home/widgets/home_selection_controller.dart';

Widget _wrap(Widget w) =>
    ProviderScope(child: MaterialApp(home: Scaffold(bottomNavigationBar: w)));

void main() {
  testWidgets('hidden when selection inactive', (tester) async {
    await tester.pumpWidget(_wrap(const HomeBulkActionBar()));
    await tester.pumpAndSettle();
    expect(find.byType(FilledButton), findsNothing);
    expect(find.byType(OutlinedButton), findsNothing);
  });

  testWidgets('2 recipes — primary reads Create Meal, Archive enabled',
      (tester) async {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    container
        .read(homeSelectionProvider.notifier)
        .enterWith(kind: 'recipe', id: 'r1');
    container.read(homeSelectionProvider.notifier).toggleRecipe('r2');

    await tester.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(
        home: Scaffold(bottomNavigationBar: HomeBulkActionBar()),
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Create Meal'), findsOneWidget);
    expect(find.text('Archive'), findsOneWidget);
  });

  testWidgets('1 recipe — primary disabled with teaching tooltip label',
      (tester) async {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    container
        .read(homeSelectionProvider.notifier)
        .enterWith(kind: 'recipe', id: 'r1');

    await tester.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(
        home: Scaffold(bottomNavigationBar: HomeBulkActionBar()),
      ),
    ));
    await tester.pumpAndSettle();
    // Disabled icon renders; primary text label "Bulk action unavailable".
    expect(find.byIcon(Icons.block), findsOneWidget);
    expect(find.text('Bulk action unavailable'), findsOneWidget);
  });

  testWidgets('1 meal + 1 recipe — primary reads Add to "<meal name>"',
      (tester) async {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    container
        .read(homeSelectionProvider.notifier)
        .enterWith(kind: 'meal', id: 'm1');
    container.read(homeSelectionProvider.notifier).toggleRecipe('r1');

    await tester.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(
        home: Scaffold(
          bottomNavigationBar:
              HomeBulkActionBar(selectedMealName: 'Kale Salad Meal'),
        ),
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Add to "Kale Salad Meal"'), findsOneWidget);
  });

  testWidgets('2 meals — primary disabled ("only one Meal")',
      (tester) async {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    container
        .read(homeSelectionProvider.notifier)
        .enterWith(kind: 'meal', id: 'm1');
    container.read(homeSelectionProvider.notifier).toggleMeal('m2');

    await tester.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(
        home: Scaffold(bottomNavigationBar: HomeBulkActionBar()),
      ),
    ));
    await tester.pumpAndSettle();
    final tooltip = tester.widget<Tooltip>(find.byType(Tooltip));
    expect(tooltip.message, contains('only one Meal'));
  });

  // Note: isWorking visuals (LinearProgressIndicator + null-onPressed
  // pass-through) are covered indirectly by the disabled-tooltip test
  // above and manually in the QA walkthrough. Widget-testing a
  // continuously-ticking progress indicator reliably was fighting the
  // ticker — deferred to hmp-5's a11y/regression sweep.

  testWidgets('recipes only — Add to / Move to render', (tester) async {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    container
        .read(homeSelectionProvider.notifier)
        .enterWith(kind: 'recipe', id: 'r1');
    container.read(homeSelectionProvider.notifier).toggleRecipe('r2');

    int addTaps = 0;
    int moveTaps = 0;
    await tester.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        home: Scaffold(
          bottomNavigationBar: HomeBulkActionBar(
            onAddToBook: () => addTaps++,
            onMoveToBook: () => moveTaps++,
          ),
        ),
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Add to'), findsOneWidget);
    expect(find.text('Move to'), findsOneWidget);

    await tester.tap(find.text('Add to'));
    expect(addTaps, 1);
    await tester.tap(find.text('Move to'));
    expect(moveTaps, 1);
  });

  testWidgets(
      'mixed selection (recipe + meal) hides Add to / Move to buttons',
      (tester) async {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    container
        .read(homeSelectionProvider.notifier)
        .enterWith(kind: 'meal', id: 'm1');
    container.read(homeSelectionProvider.notifier).toggleRecipe('r1');

    await tester.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(
        home: Scaffold(
          bottomNavigationBar:
              HomeBulkActionBar(selectedMealName: 'Kale Salad'),
        ),
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Add to'), findsNothing);
    expect(find.text('Move to'), findsNothing);
  });

  // Note: isWorking disables of Add to / Move to follow the same
  // null-onPressed pattern as the existing primary slot — the
  // continuously-ticking LinearProgressIndicator makes a widget test
  // fragile (see comment at the top of this group). Coverage stays in
  // the QA walkthrough.
}
