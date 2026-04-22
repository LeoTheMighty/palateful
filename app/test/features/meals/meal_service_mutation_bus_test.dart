// rmc-1 — MealService emits a MutationBus event on every successful
// mutation, and never emits on failure. Driver shape mirrors
// `recipe_service_test.dart` (rf-4).

import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/state/mutation_bus.dart';
import 'package:palateful/features/meals/services/meal_service.dart';

Response<dynamic> _ok(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

Map<String, dynamic> _fullMeal({
  String id = 'meal-1',
  String bookId = 'book-1',
  bool isFavorite = false,
  List<Map<String, dynamic>> components = const [],
}) =>
    {
      'id': id,
      'name': 'Weeknight Pasta',
      'recipe_book_id': bookId,
      'created_at': '2026-04-01T00:00:00Z',
      'updated_at': '2026-04-01T00:00:00Z',
      'is_favorite': isFavorite,
      'components': components,
    };

class _StubApi extends ApiClient {
  _StubApi({this.archiveShouldThrow = false});

  bool archiveShouldThrow;
  Map<String, dynamic> favoriteResponse = _fullMeal(isFavorite: true);
  Map<String, dynamic> unfavoriteResponse = _fullMeal(isFavorite: false);
  Map<String, dynamic>? restoreResponse;

  @override
  Future<Response> createMealInBook(String bookId, Map<String, dynamic> data) async =>
      _ok(_fullMeal(id: 'meal-new', bookId: bookId));

  @override
  Future<Response> updateMeal(String mealId, Map<String, dynamic> data) async =>
      _ok(_fullMeal(id: mealId));

  @override
  Future<Response> addRecipeToMeal(String mealId, Map<String, dynamic> data) async =>
      _ok(_fullMeal(id: mealId, components: [
        {'recipe_id': 'r-1', 'name': 'A', 'order_index': 0},
        {'recipe_id': data['recipe_id'], 'name': 'New', 'order_index': 1},
      ]));

  @override
  Future<Response> removeRecipeFromMeal(String mealId, String recipeId) async =>
      _ok(_fullMeal(id: mealId, components: [
        {'recipe_id': 'r-keep', 'name': 'Kept', 'order_index': 0},
      ]));

  @override
  Future<Response> reorderMealComponents(
          String mealId, Map<String, dynamic> data) async =>
      _ok(_fullMeal(id: mealId));

  @override
  Future<Response> archiveMeal(String mealId) async {
    if (archiveShouldThrow) {
      throw DioException(
        requestOptions: RequestOptions(path: ''),
        error: 'simulated 500',
      );
    }
    return _ok({'success': true, 'archived_at': '2026-04-01T00:00:00Z'});
  }

  @override
  Future<Response> restoreMeal(String mealId) async =>
      _ok(restoreResponse ?? {'success': true});

  @override
  Future<Response> favoriteMeal(String mealId) async => _ok(favoriteResponse);

  @override
  Future<Response> unfavoriteMeal(String mealId) async =>
      _ok(unfavoriteResponse);

  @override
  Future<Response> shareMeal(String mealId) async =>
      _ok({'token': 'tok-xyz', 'deep_link': 'https://x/meal/tok-xyz'});
}

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

  group('MealService emits on MutationBus', () {
    test('createMeal → MealCreated with bookId from payload', () async {
      final api = _StubApi();
      final service = MealService(api);
      final eventsFuture = _collectEvents();
      await service.createMeal(
        bookId: 'book-1',
        name: 'Pasta',
        componentRecipeIds: ['r-1', 'r-2'],
      );
      final events = await eventsFuture;
      expect(events, hasLength(1));
      final e = events.single as MealCreated;
      expect(e.mealId, 'meal-new');
      expect(e.bookId, 'book-1');
    });

    test('updateMeal → MealUpdated', () async {
      final api = _StubApi();
      final service = MealService(api);
      final eventsFuture = _collectEvents();
      await service.updateMeal('meal-1', name: 'Renamed');
      final events = await eventsFuture;
      expect(events.single, isA<MealUpdated>());
      expect((events.single as MealUpdated).mealId, 'meal-1');
    });

    test('addRecipeToMeal → MealComponentAdded with recipeId', () async {
      final api = _StubApi();
      final service = MealService(api);
      final eventsFuture = _collectEvents();
      await service.addRecipeToMeal('meal-1', recipeId: 'r-new');
      final events = await eventsFuture;
      final e = events.single as MealComponentAdded;
      expect(e.mealId, 'meal-1');
      expect(e.recipeId, 'r-new');
      expect(e.meal['components'], hasLength(2));
    });

    test('removeRecipeFromMeal → MealComponentRemoved with recipeId',
        () async {
      final api = _StubApi();
      final service = MealService(api);
      final eventsFuture = _collectEvents();
      await service.removeRecipeFromMeal('meal-1', 'r-gone');
      final events = await eventsFuture;
      final e = events.single as MealComponentRemoved;
      expect(e.mealId, 'meal-1');
      expect(e.recipeId, 'r-gone');
    });

    test('reorderMealComponents → MealComponentsReordered', () async {
      final api = _StubApi();
      final service = MealService(api);
      final eventsFuture = _collectEvents();
      await service.reorderMealComponents('meal-1', ['r-2', 'r-1']);
      final events = await eventsFuture;
      expect(events.single, isA<MealComponentsReordered>());
    });

    test('archiveMeal → MealArchived with bookId', () async {
      final api = _StubApi();
      final service = MealService(api);
      final eventsFuture = _collectEvents();
      await service.archiveMeal('meal-1', bookId: 'book-9');
      final events = await eventsFuture;
      final e = events.single as MealArchived;
      expect(e.mealId, 'meal-1');
      expect(e.bookId, 'book-9');
    });

    test('archiveMeal does NOT emit on failure', () async {
      final api = _StubApi(archiveShouldThrow: true);
      final service = MealService(api);
      final eventsFuture = _collectEvents();
      await expectLater(
        service.archiveMeal('meal-1', bookId: 'book-1'),
        throwsA(isA<DioException>()),
      );
      final events = await eventsFuture;
      expect(events, isEmpty);
    });

    test('restoreMeal (slim shape) → MealUnarchived with meal=null', () async {
      final api = _StubApi();
      final service = MealService(api);
      final eventsFuture = _collectEvents();
      await service.restoreMeal('meal-1', bookId: 'book-1');
      final events = await eventsFuture;
      final e = events.single as MealUnarchived;
      expect(e.mealId, 'meal-1');
      expect(e.bookId, 'book-1');
      expect(e.meal, isNull);
    });

    test('restoreMeal (full-meal response) → MealUnarchived with meal payload',
        () async {
      final api = _StubApi()
        ..restoreResponse = _fullMeal(id: 'meal-1');
      final service = MealService(api);
      final eventsFuture = _collectEvents();
      await service.restoreMeal('meal-1', bookId: 'book-1');
      final events = await eventsFuture;
      final e = events.single as MealUnarchived;
      expect(e.meal, isNotNull);
      expect(e.meal!['id'], 'meal-1');
    });

    test('favoriteMeal → MealFavorited(isFavorited: true) with full meal',
        () async {
      final api = _StubApi();
      final service = MealService(api);
      final eventsFuture = _collectEvents();
      await service.favoriteMeal('meal-1', bookId: 'book-1');
      final events = await eventsFuture;
      final e = events.single as MealFavorited;
      expect(e.isFavorited, true);
      expect(e.bookId, 'book-1');
      expect(e.meal, isNotNull);
    });

    test('unfavoriteMeal → MealFavorited(isFavorited: false) with full meal',
        () async {
      final api = _StubApi();
      final service = MealService(api);
      final eventsFuture = _collectEvents();
      await service.unfavoriteMeal('meal-1', bookId: 'book-1');
      final events = await eventsFuture;
      final e = events.single as MealFavorited;
      expect(e.isFavorited, false);
    });

    test('favoriteMeal with legacy slim shape → meal=null, fallback path',
        () async {
      final api = _StubApi()..favoriteResponse = {'is_favorite': true};
      final service = MealService(api);
      final eventsFuture = _collectEvents();
      await service.favoriteMeal('meal-1', bookId: 'book-1');
      final events = await eventsFuture;
      final e = events.single as MealFavorited;
      expect(e.isFavorited, true);
      expect(e.meal, isNull);
    });

    test('share → MealShared with token', () async {
      final api = _StubApi();
      final service = MealService(api);
      final eventsFuture = _collectEvents();
      await service.share('meal-1');
      final events = await eventsFuture;
      final e = events.single as MealShared;
      expect(e.mealId, 'meal-1');
      expect(e.shareToken, 'tok-xyz');
    });
  });
}
