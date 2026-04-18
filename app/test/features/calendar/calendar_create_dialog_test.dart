import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/calendar/widgets/calendar_create_dialog.dart';

void main() {
  group('CalendarCreateDialog', () {
    testWidgets('Create button is disabled when name is empty',
        (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: Scaffold(body: CalendarCreateDialog())),
        ),
      );
      await tester.pumpAndSettle();

      final createBtn = find.widgetWithText(FilledButton, 'Create');
      expect(createBtn, findsOneWidget);
      final FilledButton widget = tester.widget(createBtn);
      expect(widget.onPressed, isNull);
    });

    testWidgets('Create button enables once a name is typed', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: Scaffold(body: CalendarCreateDialog())),
        ),
      );
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField).first, 'Meal Prep');
      await tester.pump();

      final FilledButton widget =
          tester.widget(find.widgetWithText(FilledButton, 'Create'));
      expect(widget.onPressed, isNotNull);
    });
  });
}
