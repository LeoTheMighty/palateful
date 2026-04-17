import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/calendar/models/meal_event.dart';
import 'package:palateful/features/calendar/widgets/recurrence_field.dart';

void main() {
  Widget _buildField({
    RecurrenceValue? initial,
    DateTime? anchor,
    ValueChanged<RecurrenceValue?>? onChanged,
  }) {
    return MaterialApp(
      home: Scaffold(
        body: RecurrenceField(
          value: initial,
          anchorDate: anchor ?? DateTime(2026, 4, 17),
          onChanged: onChanged ?? (_) {},
        ),
      ),
    );
  }

  group('describeRecurrence', () {
    test('renders weekly summary', () {
      expect(
        describeRecurrence(const RecurrenceValue(
          interval: 'weekly',
          weekdays: ['mon', 'wed'],
        )),
        'Weekly · Mon, Wed',
      );
    });

    test('renders biweekly summary', () {
      expect(
        describeRecurrence(const RecurrenceValue(
          interval: 'biweekly',
          weekdays: ['fri'],
        )),
        'Every other week · Fri',
      );
    });

    test('renders monthly-nth summary', () {
      expect(
        describeRecurrence(const RecurrenceValue(
          interval: 'monthly',
          weekdays: ['sat'],
          monthlyNth: 'first',
        )),
        'Monthly (first Sat)',
      );
    });
  });

  group('RecurrenceField', () {
    testWidgets('renders "Repeats: Never" when value is null', (tester) async {
      await tester.pumpWidget(_buildField());
      expect(find.text('Repeats: Never'), findsOneWidget);
    });

    testWidgets('renders summary when value is set', (tester) async {
      await tester.pumpWidget(_buildField(
        initial: const RecurrenceValue(
          interval: 'weekly',
          weekdays: ['fri'],
        ),
      ));
      expect(find.text('Repeats: Weekly · Fri'), findsOneWidget);
    });

    testWidgets('tap opens the picker and Never -> null', (tester) async {
      RecurrenceValue? captured = const RecurrenceValue(
        interval: 'weekly',
        weekdays: ['fri'],
      );
      bool changed = false;

      await tester.pumpWidget(_buildField(
        initial: captured,
        onChanged: (v) {
          changed = true;
          captured = v;
        },
      ));

      await tester.tap(find.text('Repeats: Weekly · Fri'));
      await tester.pumpAndSettle();

      // Select "Never" and Done
      await tester.tap(find.text('Never'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Done'));
      await tester.pumpAndSettle();

      expect(changed, isTrue);
      expect(captured, isNull);
    });

    testWidgets(
      'picker emits a RecurrenceValue for weekly + day selected',
      (tester) async {
        RecurrenceValue? captured;
        await tester.pumpWidget(_buildField(
          onChanged: (v) => captured = v,
        ));

        await tester.tap(find.text('Repeats: Never'));
        await tester.pumpAndSettle();

        // Pick Weekly
        await tester.tap(find.text('Weekly'));
        await tester.pumpAndSettle();

        // Done
        await tester.tap(find.text('Done'));
        await tester.pumpAndSettle();

        expect(captured, isNotNull);
        expect(captured!.interval, 'weekly');
        expect(captured!.weekdays, isNotEmpty);
      },
    );
  });
}
