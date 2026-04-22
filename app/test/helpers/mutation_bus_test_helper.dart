import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/state/mutation_bus.dart';

/// Emit [event] on the app-wide [mutationBusProvider], drain pending
/// microtasks, and pump one frame. Use this inside every reactivity
/// widget test — never `pumpAndSettle(timeout)`, which introduces
/// wall-clock flake.
///
/// Shape:
///
/// ```dart
/// await pumpWithMutation(
///   tester,
///   RecipeCreated(recipeId: 'r1', recipe: {...}, bookId: 'b1'),
/// );
/// expect(find.text('r1 title'), findsOneWidget);
/// ```
///
/// Internals:
/// - `emitMutation` pushes the event onto the broadcast controller
///   (`sync: true` — subscribers wake before this returns).
/// - `tester.pump(Duration.zero)` drains microtasks so any chained
///   `ref.invalidateSelf()` starts its refetch.
/// - A second `tester.pump()` gives Riverpod's next `AsyncData` a chance
///   to rebuild the widget tree.
Future<void> pumpWithMutation(
  WidgetTester tester,
  MutationEvent event, {
  Duration frameDelay = Duration.zero,
}) async {
  emitMutation(event);
  await tester.pump(Duration.zero);
  await tester.pump(frameDelay);
}
