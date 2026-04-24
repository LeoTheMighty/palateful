import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/meals/services/meal_service.dart';

Response<dynamic> _ok(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

DioException _err({
  required int status,
  required int errorCode,
  Map<String, dynamic> data = const {},
}) {
  final resp = Response(
    requestOptions: RequestOptions(path: ''),
    statusCode: status,
    data: {
      'error_code': errorCode,
      'error_message': 'x',
      'data': data,
    },
  );
  return DioException(
    requestOptions: resp.requestOptions,
    response: resp,
    type: DioExceptionType.badResponse,
  );
}

class _FakeApi extends ApiClient {
  final Map<String, dynamic Function(List<dynamic>)> _handlers = {};

  void stubOk(String key, dynamic data) {
    _handlers[key] = (_) => _ok(data);
  }

  void stubError(String key, DioException e) {
    _handlers[key] = (_) => throw e;
  }

  dynamic _call(String key, [List<dynamic> args = const []]) {
    final h = _handlers[key];
    if (h == null) throw StateError('No stub for $key');
    return h(args);
  }

  @override
  Future<Response> listMeals({
    int? limit,
    int offset = 0,
    bool includeArchived = false,
    bool? archived,
    String? scope,
    String? q,
  }) async =>
      _call('listMeals') as Response;

  @override
  Future<Response> listMealsInBook(
    String bookId, {
    int limit = 20,
    int offset = 0,
    bool includeArchived = false,
  }) async =>
      _call('listMealsInBook', [bookId]) as Response;

  @override
  Future<Response> getMeal(String mealId) async =>
      _call('getMeal', [mealId]) as Response;

  @override
  Future<Response> createMealInBook(
          String bookId, Map<String, dynamic> data) async =>
      _call('createMealInBook', [bookId, data]) as Response;

  @override
  Future<Response> updateMeal(
          String mealId, Map<String, dynamic> data) async =>
      _call('updateMeal', [mealId, data]) as Response;

  @override
  Future<Response> archiveMeal(String mealId) async =>
      _call('archiveMeal', [mealId]) as Response;

  @override
  Future<Response> restoreMeal(String mealId) async =>
      _call('restoreMeal', [mealId]) as Response;

  @override
  Future<Response> addRecipeToMeal(
          String mealId, Map<String, dynamic> data) async =>
      _call('addRecipeToMeal', [mealId, data]) as Response;

  @override
  Future<Response> removeRecipeFromMeal(
          String mealId, String recipeId) async =>
      _call('removeRecipeFromMeal', [mealId, recipeId]) as Response;

  @override
  Future<Response> reorderMealComponents(
          String mealId, Map<String, dynamic> data) async =>
      _call('reorderMealComponents', [mealId, data]) as Response;

  @override
  Future<Response> favoriteMeal(String mealId) async =>
      _call('favoriteMeal', [mealId]) as Response;

  @override
  Future<Response> unfavoriteMeal(String mealId) async =>
      _call('unfavoriteMeal', [mealId]) as Response;
}

Map<String, dynamic> _mealPayload({String id = 'meal-1'}) => {
      'id': id,
      'name': 'Kale Salad Meal',
      'recipe_book_id': 'book-1',
      'created_at': '2026-04-18T10:00:00Z',
      'updated_at': '2026-04-18T10:00:00Z',
      'components': [
        {
          'recipe_id': 'r1',
          'name': 'Kale Salad',
          'order_index': 0,
          'available': true,
        },
        {
          'recipe_id': 'r2',
          'name': 'Lemon Dressing',
          'order_index': 1,
          'available': true,
        },
      ],
    };

void main() {
  setUpAll(() async {
  });

  late _FakeApi api;
  late MealService service;

  setUp(() {
    api = _FakeApi();
    service = MealService(api);
  });

  group('reads', () {
    test('listMealsInBook parses summary rows', () async {
      api.stubOk('listMealsInBook', {
        'items': [
          {
            'id': 'meal-1',
            'name': 'X',
            'recipe_book_id': 'b',
            'component_count': 2,
            'updated_at': '2026-04-18T10:00:00Z',
          },
        ],
        'total': 1,
      });
      final result = await service.listMealsInBook('b');
      expect(result.length, 1);
      expect(result.first.componentCount, 2);
    });

    test('listMeals parses across books', () async {
      api.stubOk('listMeals', {'items': [], 'total': 0});
      final result = await service.listMeals();
      expect(result, isEmpty);
    });

    test('getMeal parses full detail', () async {
      api.stubOk('getMeal', _mealPayload());
      final meal = await service.getMeal('meal-1');
      expect(meal.components.length, 2);
    });
  });

  group('writes — happy paths', () {
    test('createMeal', () async {
      api.stubOk('createMealInBook', _mealPayload());
      final meal = await service.createMeal(
        bookId: 'book-1',
        name: 'Kale Salad Meal',
        componentRecipeIds: ['r1', 'r2'],
      );
      expect(meal.name, 'Kale Salad Meal');
    });

    test('updateMeal', () async {
      api.stubOk('updateMeal', _mealPayload());
      final meal = await service.updateMeal('meal-1', name: 'New name');
      expect(meal.name, 'Kale Salad Meal');
    });

    test('addRecipeToMeal', () async {
      api.stubOk('addRecipeToMeal', _mealPayload());
      final meal =
          await service.addRecipeToMeal('meal-1', recipeId: 'r3');
      expect(meal.id, 'meal-1');
    });

    test('removeRecipeFromMeal', () async {
      api.stubOk('removeRecipeFromMeal', _mealPayload());
      final meal =
          await service.removeRecipeFromMeal('meal-1', 'r2');
      expect(meal.id, 'meal-1');
    });

    test('reorderMealComponents', () async {
      api.stubOk('reorderMealComponents', _mealPayload());
      final meal = await service.reorderMealComponents(
          'meal-1', ['r2', 'r1']);
      expect(meal.id, 'meal-1');
    });

    test('archiveMeal + restoreMeal', () async {
      api.stubOk('archiveMeal', {'success': true});
      api.stubOk('restoreMeal', {'success': true});
      await service.archiveMeal('meal-1', bookId: 'b');
      await service.restoreMeal('meal-1', bookId: 'b');
    });

    test('favorite + unfavorite', () async {
      api.stubOk('favoriteMeal', {'is_favorite': true});
      api.stubOk('unfavoriteMeal', {'is_favorite': false});
      expect(await service.favoriteMeal('meal-1', bookId: 'b'), true);
      expect(await service.unfavoriteMeal('meal-1', bookId: 'b'), false);
    });
  });

  group('typed exceptions', () {
    test('422 MEAL_COMPONENT_UNAVAILABLE → typed', () async {
      api.stubError(
        'createMealInBook',
        _err(
          status: 422,
          errorCode: 306,
          data: {'recipe_ids': ['r1', 'r2']},
        ),
      );
      expect(
        () => service.createMeal(
          bookId: 'b',
          name: 'X',
          componentRecipeIds: ['r1', 'r2'],
        ),
        throwsA(
          isA<MealComponentUnavailableException>()
              .having((e) => e.recipeIds, 'recipeIds', ['r1', 'r2']),
        ),
      );
    });

    test('409 MEAL_COMPONENT_DUPLICATE → typed', () async {
      api.stubError(
        'addRecipeToMeal',
        _err(status: 409, errorCode: 303),
      );
      expect(
        () => service.addRecipeToMeal('m', recipeId: 'r'),
        throwsA(isA<MealComponentDuplicateException>()),
      );
    });

    test('422 MEAL_MIN_COMPONENTS → typed', () async {
      api.stubError(
        'removeRecipeFromMeal',
        _err(status: 422, errorCode: 304),
      );
      expect(
        () => service.removeRecipeFromMeal('m', 'r'),
        throwsA(isA<MealMinComponentsException>()),
      );
    });

    test('422 MEAL_REORDER_MISMATCH → typed', () async {
      api.stubError(
        'reorderMealComponents',
        _err(status: 422, errorCode: 305),
      );
      expect(
        () => service.reorderMealComponents('m', ['r1', 'r2']),
        throwsA(isA<MealReorderMismatchException>()),
      );
    });

    test('unmapped Dio error bubbles up as-is', () async {
      api.stubError(
        'reorderMealComponents',
        _err(status: 500, errorCode: 1),
      );
      expect(
        () => service.reorderMealComponents('m', ['r1', 'r2']),
        throwsA(isA<DioException>()),
      );
    });
  });
}
