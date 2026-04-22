import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/state/mutation_bus.dart';

/// Unit tests for the MutationBus primitive.
///
/// Contract (epic rf-1 AC #6):
/// - Broadcast: multiple subscribers each receive every emitted event.
/// - No memory leak: subscribe+dispose cycles leave zero listeners on the
///   singleton controller.
/// - Ordering: two consecutive `emitMutation` calls deliver in order.
/// - Late-subscribe: events emitted before a subscriber joins are NOT
///   received (broadcast semantics, documented).
/// - No event dropped in the single-subscriber case (regression guard
///   against the original `StreamProvider.autoDispose` draft).
void main() {
  late ProviderContainer container;

  setUp(() {
    container = ProviderContainer();
  });

  tearDown(() {
    container.dispose();
  });

  group('MutationBus', () {
    test('broadcast — multiple subscribers each receive an emitted event',
        () async {
      final receivedA = <MutationEvent>[];
      final receivedB = <MutationEvent>[];

      final stream = container.read(mutationBusProvider);
      final subA = stream.listen(receivedA.add);
      final subB = stream.listen(receivedB.add);

      final event = RecipeCreated(
        recipeId: 'r1',
        recipe: const {'id': 'r1', 'name': 'Test'},
        bookId: 'b1',
      );

      emitMutation(event);
      await Future<void>.value(); // drain microtasks

      expect(receivedA, hasLength(1));
      expect(receivedB, hasLength(1));
      expect(receivedA.single, same(event));
      expect(receivedB.single, same(event));

      await subA.cancel();
      await subB.cancel();
    });

    test('no-memory-leak — 100 subscribe+dispose cycles leave zero listeners',
        () async {
      final stream = container.read(mutationBusProvider);

      for (var i = 0; i < 100; i++) {
        final sub = stream.listen((_) {});
        await sub.cancel();
      }

      expect(mutationBusHasListener(), isFalse,
          reason: 'Broadcast controller should have no active listeners '
              'after every subscriber cancels.');
    });

    test('ordering — two consecutive emits deliver in order', () async {
      final received = <MutationEvent>[];
      final stream = container.read(mutationBusProvider);
      final sub = stream.listen(received.add);

      final e1 = RecipeArchived(recipeId: 'r1', bookId: 'b1');
      final e2 = RecipeArchived(recipeId: 'r2', bookId: 'b1');

      emitMutation(e1);
      emitMutation(e2);
      await Future<void>.value();

      expect(received, [same(e1), same(e2)]);
      await sub.cancel();
    });

    test(
        'late-subscribe — events emitted before a subscriber joins are NOT '
        'received (broadcast semantics, documented)', () async {
      emitMutation(RecipeArchived(recipeId: 'pre-subscribe', bookId: 'b1'));

      final received = <MutationEvent>[];
      final stream = container.read(mutationBusProvider);
      final sub = stream.listen(received.add);

      final e = RecipeArchived(recipeId: 'post-subscribe', bookId: 'b1');
      emitMutation(e);
      await Future<void>.value();

      expect(received, [same(e)],
          reason: 'A broadcast stream does not replay past events to late '
              'subscribers.');
      await sub.cancel();
    });

    test('single-subscriber case — no event dropped (regression guard '
        'against autoDispose draft)', () async {
      final received = <MutationEvent>[];
      final stream = container.read(mutationBusProvider);
      final sub = stream.listen(received.add);

      final e = RecipeFavorited(
        recipeId: 'r-only',
        recipe: const {'id': 'r-only'},
        isFavorited: true,
      );
      emitMutation(e);
      await Future<void>.value();

      expect(received, [same(e)]);
      expect(mutationBusHasListener(), isTrue,
          reason: 'If the bus ever gets autoDispose-d, this flips false.');
      await sub.cancel();
    });

    test('emitMutation after subscriber cancels is a no-op (no throw)',
        () async {
      final received = <MutationEvent>[];
      final stream = container.read(mutationBusProvider);
      final sub = stream.listen(received.add);
      await sub.cancel();

      // Should not throw — the controller stays open (module-level
      // singleton), even with zero listeners.
      expect(
        () => emitMutation(RecipeArchived(recipeId: 'x', bookId: 'b1')),
        returnsNormally,
      );
      expect(received, isEmpty);
    });
  });
}
