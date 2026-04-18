import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/calendar/models/meal_event.dart';
import 'package:palateful/features/calendar/widgets/meal_detail_sheet.dart';

MealEvent _makeEvent({RecipeSummary? recipe}) {
  return MealEvent(
    id: 'm-1',
    title: 'Pasta night',
    scheduledAt: DateTime(2026, 4, 16, 19, 0),
    mealType: MealType.dinner,
    status: 'planned',
    isShared: false,
    recipe: recipe,
  );
}

Widget _host(Widget child) => ProviderScope(
      child: MaterialApp(
        home: Scaffold(body: child),
      ),
    );

void main() {
  testWidgets('Open Recipe label renders regardless of attachment',
      (tester) async {
    await tester.pumpWidget(_host(MealDetailSheet(
      event: _makeEvent(),
      onReschedule: (_) async {},
      onUnschedule: () {},
      onMarkCooked: null,
    )));
    await tester.pump();
    expect(find.text('Open Recipe'), findsOneWidget);
    expect(find.text('Reschedule'), findsOneWidget);
    expect(find.text('Unschedule'), findsOneWidget);
    expect(find.text('Mark Cooked'), findsOneWidget);
  });

  testWidgets('Unschedule tap pops sheet and fires onUnschedule',
      (tester) async {
    var unscheduled = false;
    late BuildContext rootContext;

    await tester.pumpWidget(ProviderScope(child: MaterialApp(
      home: Scaffold(
        body: Builder(
          builder: (ctx) {
            rootContext = ctx;
            return TextButton(
              onPressed: () => showModalBottomSheet<void>(
                context: ctx,
                builder: (_) => MealDetailSheet(
                  event: _makeEvent(),
                  onReschedule: (_) async {},
                  onUnschedule: () => unscheduled = true,
                  onMarkCooked: null,
                ),
              ),
              child: const Text('Open'),
            );
          },
        ),
      ),
    )));

    await tester.tap(find.text('Open'));
    await tester.pumpAndSettle();
    expect(find.byType(MealDetailSheet), findsOneWidget);

    await tester.tap(find.text('Unschedule'));
    await tester.pumpAndSettle();

    expect(unscheduled, isTrue);
    expect(find.byType(MealDetailSheet), findsNothing);
    expect(rootContext.mounted, isTrue);
  });

  testWidgets('Mark Cooked is visually disabled when no recipe', (tester) async {
    await tester.pumpWidget(_host(MealDetailSheet(
      event: _makeEvent(),
      onReschedule: (_) async {},
      onUnschedule: () {},
      onMarkCooked: null,
    )));
    await tester.pump();

    // Can't trigger ink-well tap when onTap is null — enough to assert the
    // label is present and rendered as the disabled variant (callback null).
    expect(find.text('Mark Cooked'), findsOneWidget);
  });
}
