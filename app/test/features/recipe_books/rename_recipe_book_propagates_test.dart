// rp-1 AC #6 — Rename propagation E2E across provider surfaces.
//
// Drives `RecipeBookService.updateRecipeBook('b1', name: 'Weeknight Wins')`
// through a mocked ApiClient and asserts that subscribers on
// `recipeBooksProvider` AND `activeRecipeBookProvider('b1')` both see
// the updated name after one frame, with no pull-to-refresh gesture.
//
// This is the core reactivity invariant for rp-1: a single mutation
// propagates to every surface that watches the data, synchronously
// within the test frame budget.

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/recipe_books/providers/recipe_books_provider.dart';
import 'package:palateful/features/recipe_books/services/recipe_book_service.dart';

Response<dynamic> _ok(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _Api extends ApiClient {
  String bookName = 'Weeknights';

  @override
  Future<Response> getRecipeBooks({int limit = 20, int offset = 0}) async =>
      _ok({
        'items': [
          {'id': 'b1', 'name': bookName, 'role': 'owner'},
        ],
      });

  @override
  Future<Response> getRecipeBook(String id) async =>
      _ok({'id': id, 'name': bookName});

  @override
  Future<Response> updateRecipeBook(
    String id,
    Map<String, dynamic> data,
  ) async {
    bookName = data['name'] as String? ?? bookName;
    return _ok({'id': id, 'name': bookName});
  }
}

void main() {
  setUpAll(() async {
  });

  late _Api api;
  late ProviderContainer container;

  setUp(() {
    final gi = GetIt.instance;
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
    if (gi.isRegistered<RecipeBookService>()) {
      gi.unregister<RecipeBookService>();
    }
    api = _Api();
    gi.registerSingleton<ApiClient>(api);
    gi.registerLazySingleton<RecipeBookService>(
      () => RecipeBookService(gi<ApiClient>()),
    );
    container = ProviderContainer();
  });

  tearDown(() {
    container.dispose();
    final gi = GetIt.instance;
    if (gi.isRegistered<RecipeBookService>()) {
      gi.unregister<RecipeBookService>();
    }
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  });

  test('rename propagates to recipeBooksProvider AND activeRecipeBookProvider',
      () async {
    // Seed: two subscribers reading pre-rename state.
    final initialList = await container.read(recipeBooksProvider.future);
    final initialDetail =
        await container.read(activeRecipeBookProvider('b1').future);
    expect(initialList.single['name'], 'Weeknights');
    expect(initialDetail['name'], 'Weeknights');

    // Drive the mutation. Service emits RecipeBookUpdated on the bus;
    // both providers are subscribed and invalidate.
    await Future<void>.delayed(Duration.zero);
    await GetIt.instance<RecipeBookService>()
        .updateRecipeBook('b1', {'name': 'Weeknight Wins'});
    await Future<void>.delayed(Duration.zero);

    // Both providers re-read through the fake API.
    final nextList = await container.read(recipeBooksProvider.future);
    final nextDetail =
        await container.read(activeRecipeBookProvider('b1').future);
    expect(nextList.single['name'], 'Weeknight Wins');
    expect(nextDetail['name'], 'Weeknight Wins');
  });
}
