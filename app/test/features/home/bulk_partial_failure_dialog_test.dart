import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/home/widgets/bulk_dispatcher.dart';
import 'package:palateful/features/home/widgets/bulk_partial_failure_dialog.dart';

Future<void> _openDialog(
  WidgetTester tester, {
  required BulkOperation op,
  required List<BulkOperationResult> results,
}) async {
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(
      body: Builder(
        builder: (context) => ElevatedButton(
          onPressed: () => BulkPartialFailureDialog.show(
            context,
            operation: op,
            results: results,
          ),
          child: const Text('open'),
        ),
      ),
    ),
  ));
  await tester.tap(find.text('open'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('addToMeal — renders failures only with proper title',
      (tester) async {
    await _openDialog(
      tester,
      op: BulkOperation.addToMeal,
      results: const [
        BulkOperationResult(targetName: 'Good', success: true),
        BulkOperationResult(
          targetName: 'Bad',
          success: false,
          errorReason: "You can't edit this recipe",
        ),
      ],
    );
    expect(find.text('Some recipes could not be added'), findsOneWidget);
    expect(find.text('Bad'), findsOneWidget);
    expect(find.text("You can't edit this recipe"), findsOneWidget);
    expect(find.text('Good'), findsNothing);
  });

  testWidgets('archive — title matches operation', (tester) async {
    await _openDialog(
      tester,
      op: BulkOperation.archive,
      results: const [
        BulkOperationResult(
          targetName: 'Kale Salad',
          success: false,
          errorReason: 'Conflict — try again',
        ),
      ],
    );
    expect(find.text('Some items could not be archived'), findsOneWidget);
    expect(find.text('Kale Salad'), findsOneWidget);
    expect(find.text('Conflict — try again'), findsOneWidget);
  });

  testWidgets('empty reason falls back to "Unknown error"',
      (tester) async {
    await _openDialog(
      tester,
      op: BulkOperation.archive,
      results: const [
        BulkOperationResult(targetName: 'Meal A', success: false),
      ],
    );
    expect(find.text('Unknown error'), findsOneWidget);
  });

  testWidgets('Dismiss button pops the dialog', (tester) async {
    await _openDialog(
      tester,
      op: BulkOperation.archive,
      results: const [
        BulkOperationResult(
          targetName: 'Meal A',
          success: false,
          errorReason: 'Conflict — try again',
        ),
      ],
    );
    await tester.tap(find.text('Dismiss'));
    await tester.pumpAndSettle();
    expect(find.text('Some items could not be archived'), findsNothing);
  });
}
