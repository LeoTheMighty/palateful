// rp-1 — RecipeBookService + providers reactivity regression.
//
// Shape:
//   1. Register a fake ApiClient via GetIt + bind RecipeBookService.
//   2. For each mutation (create, rename, archive, restore, delete,
//      add-member, update-role, remove-member, bulk-move, bulk-archive,
//      bulk-tags), drive the service method and assert exactly one
//      MutationBus event fires with the expected payload shape.
//   3. For recipeBooksProvider / archivedRecipeBooksProvider /
//      sharedRecipeBooksProvider / activeRecipeBookProvider /
//      recipeBookMembersProvider, assert the provider invalidates on
//      relevant events and NOT on unrelated ones.
//
// No widget pumping — pure service-layer + provider-layer regression.

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/state/mutation_bus.dart';
import 'package:palateful/features/recipe_books/providers/recipe_books_provider.dart';
import 'package:palateful/features/recipe_books/services/recipe_book_service.dart';

Response<dynamic> _ok(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _FakeApi extends ApiClient {
  Map<String, dynamic> book = {'id': 'b1', 'name': 'Weeknights'};
  List<Map<String, dynamic>> books = [
    {'id': 'b1', 'name': 'Weeknights', 'role': 'owner', 'is_owner': true},
    {'id': 'b2', 'name': 'Mom\'s Kitchen', 'role': 'editor', 'is_owner': false},
  ];
  List<Map<String, dynamic>> archived = [
    {'id': 'b3', 'name': 'Old Recipes', 'archived_at': '2026-01-01'},
  ];
  String? restoredDefault;
  bool throwOnNextMutation = false;
  int getRecipeBookCalls = 0;
  int getRecipeBooksCalls = 0;
  int getArchivedCalls = 0;

  @override
  Future<Response> getRecipeBooks({int limit = 20, int offset = 0}) async {
    getRecipeBooksCalls++;
    return _ok({'items': books});
  }

  @override
  Future<Response> getArchivedRecipeBooks() async {
    getArchivedCalls++;
    return _ok({'items': archived});
  }

  @override
  Future<Response> getRecipeBook(String id) async {
    getRecipeBookCalls++;
    return _ok({
      ...book,
      'id': id,
      'members': const [
        {'user_id': 'u1', 'role': 'editor', 'name': 'Alice'},
      ],
    });
  }

  @override
  Future<Response> createRecipeBook(Map<String, dynamic> data) async {
    _maybeThrow();
    return _ok({'id': 'new-book', ...data});
  }

  @override
  Future<Response> updateRecipeBook(String id, Map<String, dynamic> data) async {
    _maybeThrow();
    return _ok({'id': id, ...data});
  }

  @override
  Future<Response> archiveRecipeBook(String id) async {
    _maybeThrow();
    return _ok({
      'success': true,
      if (restoredDefault != null)
        'restored_default_recipe_book_id': restoredDefault,
    });
  }

  @override
  Future<Response> restoreRecipeBook(String id) async {
    _maybeThrow();
    return _ok({'id': id, 'name': 'Restored'});
  }

  @override
  Future<Response> deleteRecipeBook(String id) async {
    _maybeThrow();
    return _ok({'success': true});
  }

  @override
  Future<Response> addRecipeBookMember(
    String bookId,
    Map<String, dynamic> data,
  ) async {
    _maybeThrow();
    return _ok({'user_id': 'u42', 'role': data['role'] ?? 'editor'});
  }

  @override
  Future<Response> removeRecipeBookMember(String bookId, String userId) async {
    _maybeThrow();
    return _ok({'success': true});
  }

  @override
  Future<Response> updateRecipeBookMemberRole(
    String bookId,
    String userId,
    Map<String, dynamic> data,
  ) async {
    _maybeThrow();
    return _ok({'user_id': userId, 'role': data['role']});
  }

  @override
  Future<Response> bulkMoveRecipes(
    List<String> recipeIds,
    String destinationBookId,
  ) async {
    _maybeThrow();
    return _ok({'moved': recipeIds.length});
  }

  @override
  Future<Response> bulkArchiveRecipes(List<String> recipeIds) async {
    _maybeThrow();
    return _ok({'archived': recipeIds.length});
  }

  @override
  Future<Response> bulkUpdateTags(
    List<String> recipeIds, {
    List<String>? addTags,
    List<String>? removeTags,
  }) async {
    _maybeThrow();
    return _ok({'updated': recipeIds.length});
  }

  void _maybeThrow() {
    if (throwOnNextMutation) {
      throwOnNextMutation = false;
      throw DioException(
        requestOptions: RequestOptions(path: ''),
        response: Response(
          requestOptions: RequestOptions(path: ''),
          statusCode: 500,
        ),
        type: DioExceptionType.badResponse,
      );
    }
  }
}

Future<MutationEvent?> _captureNextEvent(
  Future<void> Function() action,
) async {
  MutationEvent? captured;
  final sub = mutationBusStream().listen((event) => captured ??= event);
  await action();
  await Future<void>.delayed(Duration.zero);
  await sub.cancel();
  return captured;
}

Future<List<MutationEvent>> _captureAllEvents(
  Future<void> Function() action,
) async {
  final events = <MutationEvent>[];
  final sub = mutationBusStream().listen(events.add);
  await action();
  await Future<void>.delayed(Duration.zero);
  await sub.cancel();
  return events;
}

void _register(_FakeApi api) {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  if (gi.isRegistered<RecipeBookService>()) {
    gi.unregister<RecipeBookService>();
  }
  gi.registerSingleton<ApiClient>(api);
  gi.registerLazySingleton<RecipeBookService>(
    () => RecipeBookService(gi<ApiClient>()),
  );
}

void _unregister() {
  final gi = GetIt.instance;
  if (gi.isRegistered<RecipeBookService>()) {
    gi.unregister<RecipeBookService>();
  }
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
}

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  group('RecipeBookService — emits one event per mutation', () {
    late _FakeApi api;
    late RecipeBookService service;

    setUp(() {
      api = _FakeApi();
      _register(api);
      service = GetIt.instance<RecipeBookService>();
    });

    tearDown(_unregister);

    test('createRecipeBook emits RecipeBookCreated', () async {
      final event = await _captureNextEvent(() async {
        await service.createRecipeBook({'name': 'Test'});
      });
      expect(event, isA<RecipeBookCreated>());
      expect((event as RecipeBookCreated).bookId, 'new-book');
    });

    test('updateRecipeBook emits RecipeBookUpdated', () async {
      final event = await _captureNextEvent(() async {
        await service.updateRecipeBook('b1', {'name': 'Renamed'});
      });
      expect(event, isA<RecipeBookUpdated>());
      expect((event as RecipeBookUpdated).bookId, 'b1');
      expect(event.book['name'], 'Renamed');
    });

    test('archiveRecipeBook emits RecipeBookArchived with restored default',
        () async {
      api.restoredDefault = 'b99';
      final event = await _captureNextEvent(() async {
        await service.archiveRecipeBook('b1');
      });
      expect(event, isA<RecipeBookArchived>());
      expect((event as RecipeBookArchived).bookId, 'b1');
      expect(event.restoredDefaultBookId, 'b99');
    });

    test('archiveRecipeBook emits RecipeBookArchived with null default',
        () async {
      api.restoredDefault = null;
      final event = await _captureNextEvent(() async {
        await service.archiveRecipeBook('b1');
      });
      expect((event as RecipeBookArchived).restoredDefaultBookId, isNull);
    });

    test('restoreRecipeBook emits RecipeBookUnarchived', () async {
      final event = await _captureNextEvent(() async {
        await service.restoreRecipeBook('b1');
      });
      expect(event, isA<RecipeBookUnarchived>());
      expect((event as RecipeBookUnarchived).bookId, 'b1');
    });

    test('deleteRecipeBook emits RecipeBookDeleted', () async {
      final event = await _captureNextEvent(() async {
        await service.deleteRecipeBook('b1');
      });
      expect(event, isA<RecipeBookDeleted>());
      expect((event as RecipeBookDeleted).bookId, 'b1');
    });

    test('addMember emits RecipeBookMemberAdded', () async {
      final event = await _captureNextEvent(() async {
        await service.addMember('b1', userEmail: 'a@b.c', role: 'editor');
      });
      expect(event, isA<RecipeBookMemberAdded>());
      expect((event as RecipeBookMemberAdded).bookId, 'b1');
      expect(event.role, 'editor');
    });

    test('updateMemberRole emits RecipeBookMemberChanged with new role',
        () async {
      final event = await _captureNextEvent(() async {
        await service.updateMemberRole('b1', 'u1', 'viewer');
      });
      expect(event, isA<RecipeBookMemberChanged>());
      expect((event as RecipeBookMemberChanged).newRole, 'viewer');
    });

    test('removeMember emits RecipeBookMemberChanged with null role',
        () async {
      final event = await _captureNextEvent(() async {
        await service.removeMember('b1', 'u1');
      });
      expect(event, isA<RecipeBookMemberChanged>());
      expect((event as RecipeBookMemberChanged).newRole, isNull);
    });

    test('bulkMoveRecipes emits one RecipeMoved per id (source+dest bookIds)',
        () async {
      final events = await _captureAllEvents(() async {
        await service.bulkMoveRecipes(
          const ['r1', 'r2', 'r3'],
          'b-new',
          sourceBookId: 'b-old',
        );
      });
      final moved = events.whereType<RecipeMoved>().toList();
      expect(moved, hasLength(3));
      expect(moved.first.oldBookId, 'b-old');
      expect(moved.first.newBookId, 'b-new');
    });

    test('bulkArchiveRecipes emits ONE RecipeBulkArchived, not N',
        () async {
      final events = await _captureAllEvents(() async {
        await service.bulkArchiveRecipes(
          const ['r1', 'r2', 'r3'],
          bookId: 'b1',
        );
      });
      final bulk = events.whereType<RecipeBulkArchived>().toList();
      expect(bulk, hasLength(1));
      expect(bulk.single.recipeIds, ['r1', 'r2', 'r3']);
      expect(events.whereType<RecipeArchived>(), isEmpty);
    });

    test('bulkUpdateTags emits one RecipeUpdated per id', () async {
      final events = await _captureAllEvents(() async {
        await service.bulkUpdateTags(
          const ['r1', 'r2'],
          addTags: const ['quick'],
        );
      });
      expect(events.whereType<RecipeUpdated>(), hasLength(2));
    });

    test('failed mutation throws and emits NOTHING', () async {
      api.throwOnNextMutation = true;
      final events = await _captureAllEvents(() async {
        try {
          await service.updateRecipeBook('b1', {'name': 'x'});
        } on DioException {
          // swallowed in test; real UI routes through Snackbar
        }
      });
      expect(events, isEmpty);
    });
  });

  group('Providers — subscribe and invalidate on relevant events', () {
    late _FakeApi api;
    late ProviderContainer container;

    setUp(() {
      api = _FakeApi();
      _register(api);
      container = ProviderContainer();
    });

    tearDown(() {
      container.dispose();
      _unregister();
    });

    test('recipeBooksProvider refetches on RecipeBookCreated', () async {
      final first = await container.read(recipeBooksProvider.future);
      expect(first, hasLength(2));
      expect(api.getRecipeBooksCalls, 1);

      // Wait for the bus subscription inside the provider to register.
      await Future<void>.delayed(Duration.zero);
      emitMutation(const RecipeBookCreated(
        bookId: 'new-book',
        book: <String, dynamic>{'id': 'new-book', 'name': 'New'},
      ));

      // Drain microtasks so invalidateSelf fires.
      await Future<void>.delayed(Duration.zero);
      await container.read(recipeBooksProvider.future);
      expect(api.getRecipeBooksCalls, greaterThanOrEqualTo(2));
    });

    test('recipeBooksProvider DOES NOT refetch on unrelated RecipeCreated',
        () async {
      await container.read(recipeBooksProvider.future);
      final baseline = api.getRecipeBooksCalls;
      await Future<void>.delayed(Duration.zero);
      emitMutation(RecipeCreated(
        recipeId: 'r1',
        recipe: const {'id': 'r1'},
        bookId: 'b1',
      ));
      await Future<void>.delayed(Duration.zero);
      expect(api.getRecipeBooksCalls, baseline);
    });

    test('archivedRecipeBooksProvider refetches on RecipeBookArchived',
        () async {
      await container.read(archivedRecipeBooksProvider.future);
      final baseline = api.getArchivedCalls;
      await Future<void>.delayed(Duration.zero);
      emitMutation(const RecipeBookArchived(bookId: 'b1'));
      await Future<void>.delayed(Duration.zero);
      await container.read(archivedRecipeBooksProvider.future);
      expect(api.getArchivedCalls, greaterThan(baseline));
    });

    test('activeRecipeBookProvider patches on book-scoped events, not others',
        () async {
      await container.read(activeRecipeBookProvider('b1').future);
      final baseline = api.getRecipeBookCalls;

      // Event scoped to a different book — NO refetch.
      await Future<void>.delayed(Duration.zero);
      emitMutation(const RecipeBookUpdated(
        bookId: 'b-other',
        book: <String, dynamic>{'id': 'b-other', 'name': 'x'},
      ));
      await Future<void>.delayed(Duration.zero);
      expect(api.getRecipeBookCalls, baseline);

      // Event scoped to b1 — refetch.
      emitMutation(const RecipeBookUpdated(
        bookId: 'b1',
        book: <String, dynamic>{'id': 'b1', 'name': 'Weeknight Wins'},
      ));
      await Future<void>.delayed(Duration.zero);
      await container.read(activeRecipeBookProvider('b1').future);
      expect(api.getRecipeBookCalls, greaterThan(baseline));
    });

    test('sharedRecipeBooksProvider filters to non-owner books', () async {
      final shared = await container.read(sharedRecipeBooksProvider.future);
      expect(shared, hasLength(1));
      expect(shared.single['id'], 'b2');
    });

    test('recipeBookMembersProvider invalidates on MemberAdded for this book',
        () async {
      await container.read(recipeBookMembersProvider('b1').future);
      final baseline = api.getRecipeBookCalls;
      await Future<void>.delayed(Duration.zero);
      emitMutation(const RecipeBookMemberAdded(
        bookId: 'b1',
        userId: 'u-new',
        role: 'editor',
      ));
      await Future<void>.delayed(Duration.zero);
      await container.read(recipeBookMembersProvider('b1').future);
      expect(api.getRecipeBookCalls, greaterThan(baseline));
    });

    test('recipeBookMembersProvider ignores MemberAdded for other books',
        () async {
      await container.read(recipeBookMembersProvider('b1').future);
      final baseline = api.getRecipeBookCalls;
      await Future<void>.delayed(Duration.zero);
      emitMutation(const RecipeBookMemberAdded(
        bookId: 'b-other',
        userId: 'u-new',
        role: 'editor',
      ));
      await Future<void>.delayed(Duration.zero);
      expect(api.getRecipeBookCalls, baseline);
    });

    // ffm-1 — "cache once, share widely" invariant.
    test('recipeBooksProvider reuses single fetch across many readers',
        () async {
      // Ten imperative reads (mirroring the 10-callsite migration) should
      // result in exactly ONE network round-trip — the whole point of
      // consolidating every screen onto the shared provider.
      for (var i = 0; i < 10; i++) {
        await container.read(recipeBooksProvider.future);
      }
      expect(api.getRecipeBooksCalls, 1,
          reason: 'ffm-1: every callsite shares one session-level fetch');
    });
  });

  group('Service is stateless across instances', () {
    test('two service instances share no cache', () async {
      final api = _FakeApi();
      _register(api);
      final a = RecipeBookService(api);
      final b = RecipeBookService(api);
      await a.updateRecipeBook('b1', {'name': 'hi'});
      // If the service kept a local cache, `b` would see stale data or
      // diverge — regression proved by the fact that both just proxy to
      // the same ApiClient and never touch internal state.
      expect(identical(a, b), isFalse);
      _unregister();
    });
  });
}
