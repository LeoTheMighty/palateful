// rf-4 — RecipeService emits a MutationBus event on every successful
// mutation, and never emits on failure.
//
// Driver: fake ApiClient returning deterministic 200/failure; service
// is instantiated with that fake and its methods are invoked. Each
// test subscribes to `mutationBusProvider` via `ref.read(...).listen`
// and asserts the subclass + payload shape of the next-delivered
// event.

import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/state/mutation_bus.dart';
import 'package:palateful/features/recipes/services/recipe_service.dart';

Response<dynamic> _ok(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _StubApi extends ApiClient {
  _StubApi({
    this.createResponse,
    this.updateResponse,
    this.toggleResponse,
    this.forkResponse,
    this.moveResponse,
    this.copyResponse,
    this.restoreResponse,
    this.bulkArchiveShouldThrow = false,
    this.deleteShouldThrow = false,
  });

  Map<String, dynamic>? createResponse;
  Map<String, dynamic>? updateResponse;
  Map<String, dynamic>? toggleResponse;
  Map<String, dynamic>? forkResponse;
  Map<String, dynamic>? moveResponse;
  Map<String, dynamic>? copyResponse;
  Map<String, dynamic>? restoreResponse;
  bool bulkArchiveShouldThrow;
  bool deleteShouldThrow;

  @override
  Future<Response> createRecipe(String bookId, Map<String, dynamic> data) async =>
      _ok(createResponse ?? {'id': 'r-new', 'name': 'New'});

  @override
  Future<Response> updateRecipe(String recipeId, Map<String, dynamic> data) async =>
      _ok(updateResponse ?? {'id': recipeId, 'primary_vibe': 'comfort'});

  @override
  Future<Response> deleteRecipe(String recipeId) async {
    if (deleteShouldThrow) {
      throw DioException(
        requestOptions: RequestOptions(path: ''),
        error: 'simulated 500',
      );
    }
    return _ok({'ok': true});
  }

  @override
  Future<Response> restoreRecipe(String recipeId) async =>
      _ok(restoreResponse ?? {'id': recipeId, 'name': 'Restored'});

  @override
  Future<Response> toggleFavorite(String recipeId) async =>
      _ok(toggleResponse ?? {'id': recipeId, 'name': 'Fav', 'is_favorite': true});

  @override
  Future<Response> forkRecipe(String recipeId, String destinationBookId) async =>
      _ok(forkResponse ?? {'id': 'r-forked', 'name': 'Forked'});

  @override
  Future<Response> moveRecipe(String recipeId, String destinationBookId) async =>
      _ok(moveResponse ?? {'id': recipeId, 'recipe_book_id': destinationBookId});

  @override
  Future<Response> copyRecipe(String recipeId, String destinationBookId) async =>
      _ok(copyResponse ?? {'id': 'r-copied', 'name': 'Copy'});

  @override
  Future<Response> bulkArchiveRecipes(List<String> recipeIds) async {
    if (bulkArchiveShouldThrow) {
      throw DioException(
        requestOptions: RequestOptions(path: ''),
        error: 'simulated 500',
      );
    }
    return _ok({'archived': recipeIds.length});
  }

  @override
  Future<Response> addRecipeNote(String recipeId, String body) async =>
      _ok({'id': 'n-1', 'body': body});

  @override
  Future<Response> deleteRecipeNote(String recipeId, String noteId) async =>
      _ok({'ok': true});
}

/// Collect the next N events emitted on [mutationBusProvider]. Returns a
/// `Future<List<MutationEvent>>` that completes once N events arrive.
Future<List<MutationEvent>> _collectEvents({int take = 1}) {
  final buf = <MutationEvent>[];
  late StreamSubscription<MutationEvent> sub;
  final completer = Completer<List<MutationEvent>>();
  sub = _bus().listen((event) {
    buf.add(event);
    if (buf.length >= take) {
      completer.complete(List.of(buf));
      sub.cancel();
    }
  });
  return completer.future.timeout(
    const Duration(seconds: 1),
    onTimeout: () {
      sub.cancel();
      return List.of(buf);
    },
  );
}

Stream<MutationEvent> _bus() {
  // The module-level singleton is exposed indirectly via
  // `mutationBusProvider`; reach into the provider at test time by
  // creating an ad-hoc Riverpod-free consumer — just call the top-level
  // `emitMutation` + listen via a fresh listener on the broadcast.
  // For tests we have a simpler handle: the event flow via the public
  // [mutationBusProvider] read in the production code. Here we
  // subscribe via the provider's underlying stream using the exported
  // [emitMutation] path indirectly — in tests `emitMutation` and
  // `mutationBusProvider.listen` round-trip through the same
  // singleton.
  //
  // Since [mutationBusProvider] is a Riverpod provider, the cleanest
  // test-time read is through a `ProviderContainer`.
  final container = _container ??= ProviderContainer();
  return container.read(mutationBusProvider);
}

ProviderContainer? _container;

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  tearDown(() {
    _container?.dispose();
    _container = null;
  });

  group('RecipeService', () {
    test('createRecipe emits RecipeCreated with full payload + bookId',
        () async {
      final api = _StubApi(
        createResponse: {'id': 'r-77', 'name': 'Pasta'},
      );
      final service = RecipeService(api);

      final eventsFuture = _collectEvents();
      await service.createRecipe('book-1', {'name': 'Pasta'});
      final events = await eventsFuture;

      expect(events, hasLength(1));
      final e = events.single as RecipeCreated;
      expect(e.recipeId, 'r-77');
      expect(e.bookId, 'book-1');
      expect(e.recipe['name'], 'Pasta');
    });

    test('updateRecipe emits RecipeUpdated', () async {
      final api = _StubApi();
      final service = RecipeService(api);

      final eventsFuture = _collectEvents();
      await service.updateRecipe('r-1', {'primary_vibe': 'comfort'});
      final events = await eventsFuture;

      expect(events.single, isA<RecipeUpdated>());
      expect((events.single as RecipeUpdated).recipeId, 'r-1');
    });

    test('archiveRecipe emits RecipeArchived on success', () async {
      final api = _StubApi();
      final service = RecipeService(api);

      final eventsFuture = _collectEvents();
      await service.archiveRecipe('r-1', bookId: 'book-1');
      final events = await eventsFuture;

      final e = events.single as RecipeArchived;
      expect(e.recipeId, 'r-1');
      expect(e.bookId, 'book-1');
    });

    test('archiveRecipe does NOT emit on failure', () async {
      final api = _StubApi(deleteShouldThrow: true);
      final service = RecipeService(api);

      final eventsFuture = _collectEvents();
      await expectLater(
        service.archiveRecipe('r-1', bookId: 'book-1'),
        throwsA(isA<DioException>()),
      );
      final events = await eventsFuture;
      expect(events, isEmpty);
    });

    test('toggleFavorite emits RecipeFavorited with isFavorited from payload',
        () async {
      final api = _StubApi(
        toggleResponse: {
          'id': 'r-5',
          'name': 'Soup',
          'is_favorite': true,
        },
      );
      final service = RecipeService(api);

      final eventsFuture = _collectEvents();
      await service.toggleFavorite('r-5');
      final events = await eventsFuture;

      final e = events.single as RecipeFavorited;
      expect(e.recipeId, 'r-5');
      expect(e.isFavorited, true);
      expect(e.recipe['name'], 'Soup');
    });

    test('forkRecipe emits RecipeForked with parentRecipeId', () async {
      final api = _StubApi(
        forkResponse: {'id': 'r-child', 'name': 'Variant'},
      );
      final service = RecipeService(api);

      final eventsFuture = _collectEvents();
      await service.forkRecipe('r-parent', 'book-2');
      final events = await eventsFuture;

      final e = events.single as RecipeForked;
      expect(e.recipeId, 'r-child');
      expect(e.parentRecipeId, 'r-parent');
    });

    test('moveRecipe emits RecipeMoved with both book ids', () async {
      final api = _StubApi(
        moveResponse: {'id': 'r-1', 'recipe_book_id': 'book-b'},
      );
      final service = RecipeService(api);

      final eventsFuture = _collectEvents();
      await service.moveRecipe('r-1', 'book-b', oldBookId: 'book-a');
      final events = await eventsFuture;

      final e = events.single as RecipeMoved;
      expect(e.oldBookId, 'book-a');
      expect(e.newBookId, 'book-b');
    });

    test('bulkArchiveRecipes emits ONE RecipeBulkArchived, not N RecipeArchived',
        () async {
      final api = _StubApi();
      final service = RecipeService(api);

      final eventsFuture = _collectEvents(take: 1);
      await service.bulkArchiveRecipes(
        ['r-1', 'r-2', 'r-3'],
        bookId: 'book-1',
      );
      final events = await eventsFuture;

      expect(events, hasLength(1));
      final e = events.single as RecipeBulkArchived;
      expect(e.recipeIds, ['r-1', 'r-2', 'r-3']);
      expect(e.bookId, 'book-1');
    });

    test('bulkArchiveRecipes emits nothing on failure', () async {
      final api = _StubApi(bulkArchiveShouldThrow: true);
      final service = RecipeService(api);

      final eventsFuture = _collectEvents();
      await expectLater(
        service.bulkArchiveRecipes(['r-1'], bookId: 'book-1'),
        throwsA(isA<DioException>()),
      );
      final events = await eventsFuture;
      expect(events, isEmpty);
    });

    test('addRecipeNote emits RecipeUpdated (notes are part of the resource)',
        () async {
      final api = _StubApi();
      final service = RecipeService(api);

      final eventsFuture = _collectEvents();
      await service.addRecipeNote('r-1', 'cooked it twice');
      final events = await eventsFuture;

      expect(events.single, isA<RecipeUpdated>());
    });

    test('deleteRecipeNote emits RecipeUpdated', () async {
      final api = _StubApi();
      final service = RecipeService(api);

      final eventsFuture = _collectEvents();
      await service.deleteRecipeNote('r-1', 'n-99');
      final events = await eventsFuture;

      expect(events.single, isA<RecipeUpdated>());
    });
  });
}
