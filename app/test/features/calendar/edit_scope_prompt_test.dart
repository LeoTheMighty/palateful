import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/calendar/widgets/edit_scope_prompt.dart';

Future<EditScope?> _openAndTap(
  WidgetTester tester, {
  required EditAction action,
  required String tapLabel,
}) async {
  EditScope? result;
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(
      body: Builder(
        builder: (ctx) => TextButton(
          onPressed: () async {
            result = await showEditScopePrompt(ctx, action: action);
          },
          child: const Text('Open'),
        ),
      ),
    ),
  ));
  await tester.tap(find.text('Open'));
  await tester.pumpAndSettle();
  await tester.tap(find.text(tapLabel));
  await tester.pumpAndSettle();
  return result;
}

void main() {
  group('EditScopePrompt', () {
    testWidgets('renders the three scope choices', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (ctx) => TextButton(
              onPressed: () =>
                  showEditScopePrompt(ctx, action: EditAction.reschedule),
              child: const Text('Open'),
            ),
          ),
        ),
      ));
      await tester.tap(find.text('Open'));
      await tester.pumpAndSettle();

      expect(find.text('This occurrence'), findsOneWidget);
      expect(find.text('This and following'), findsOneWidget);
      expect(find.text('All occurrences'), findsOneWidget);
      expect(find.text('Cancel'), findsOneWidget);
    });

    testWidgets('returns thisOccurrence on tap', (tester) async {
      final result = await _openAndTap(
        tester,
        action: EditAction.reschedule,
        tapLabel: 'This occurrence',
      );
      expect(result, EditScope.thisOccurrence);
    });

    testWidgets('returns thisAndFollowing on tap', (tester) async {
      final result = await _openAndTap(
        tester,
        action: EditAction.unschedule,
        tapLabel: 'This and following',
      );
      expect(result, EditScope.thisAndFollowing);
    });

    testWidgets('returns all on tap', (tester) async {
      final result = await _openAndTap(
        tester,
        action: EditAction.reschedule,
        tapLabel: 'All occurrences',
      );
      expect(result, EditScope.all);
    });

    testWidgets('Cancel returns null', (tester) async {
      final result = await _openAndTap(
        tester,
        action: EditAction.reschedule,
        tapLabel: 'Cancel',
      );
      expect(result, isNull);
    });

    testWidgets('unschedule subtitles are action-flavored', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (ctx) => TextButton(
              onPressed: () =>
                  showEditScopePrompt(ctx, action: EditAction.unschedule),
              child: const Text('Open'),
            ),
          ),
        ),
      ));
      await tester.tap(find.text('Open'));
      await tester.pumpAndSettle();

      expect(find.textContaining('removed'), findsWidgets);
    });

    testWidgets('recipeSwap action subtitles differ', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (ctx) => TextButton(
              onPressed: () =>
                  showEditScopePrompt(ctx, action: EditAction.recipeSwap),
              child: const Text('Open'),
            ),
          ),
        ),
      ));
      await tester.tap(find.text('Open'));
      await tester.pumpAndSettle();

      expect(find.textContaining('changes'), findsWidgets);
    });
  });
}
