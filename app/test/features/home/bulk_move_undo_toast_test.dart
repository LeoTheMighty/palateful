import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/home/widgets/bulk_move_undo_toast.dart';

void main() {
  testWidgets('renders count + destination + Undo action', (tester) async {
    int undoTaps = 0;
    late BuildContext capturedContext;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: Builder(builder: (ctx) {
          capturedContext = ctx;
          return const SizedBox();
        }),
      ),
    ));
    showBulkMoveUndoToast(
      capturedContext,
      movedCount: 5,
      destinationName: 'Favorites',
      onUndo: () => undoTaps++,
    );
    // Two pumps: one to schedule the snackbar, one to run its enter
    // animation enough that the action button is hit-testable.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 750));

    expect(find.text('Moved 5 recipes to Favorites'), findsOneWidget);
    expect(find.text('Undo'), findsOneWidget);

    await tester.tap(find.text('Undo'));
    expect(undoTaps, 1);
  });

  testWidgets('singularizes copy at count == 1', (tester) async {
    late BuildContext capturedContext;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: Builder(builder: (ctx) {
          capturedContext = ctx;
          return const SizedBox();
        }),
      ),
    ));
    showBulkMoveUndoToast(
      capturedContext,
      movedCount: 1,
      destinationName: "Mom's Recipes",
      onUndo: () {},
    );
    await tester.pump();
    expect(find.text("Moved 1 recipe to Mom's Recipes"), findsOneWidget);
  });
}
