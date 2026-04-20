import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/home/widgets/bulk_dispatcher.dart';
import 'package:palateful/features/meals/services/meal_service.dart';

DioException _dio(int status) => DioException(
      requestOptions: RequestOptions(path: ''),
      response: Response(
        statusCode: status,
        requestOptions: RequestOptions(path: ''),
      ),
      type: DioExceptionType.badResponse,
    );

void main() {
  group('explainBulkError', () {
    test('MealComponentDuplicateException → "Already in this Meal"', () {
      expect(
        explainBulkError(
          MealComponentDuplicateException(),
          BulkOperation.addToMeal,
        ),
        'Already in this Meal',
      );
    });

    test('MealComponentUnavailableException → "no longer available"', () {
      expect(
        explainBulkError(
          MealComponentUnavailableException(['r1']),
          BulkOperation.addToMeal,
        ),
        'Recipe is no longer available',
      );
    });

    test('Dio 403 add-to-meal → "You can\'t edit this recipe"', () {
      expect(
        explainBulkError(_dio(403), BulkOperation.addToMeal),
        "You can't edit this recipe",
      );
    });

    test('Dio 403 archive → "You can\'t archive this"', () {
      expect(
        explainBulkError(_dio(403), BulkOperation.archive),
        "You can't archive this",
      );
    });

    test('Dio 404 → "No longer available"', () {
      expect(
        explainBulkError(_dio(404), BulkOperation.archive),
        'No longer available',
      );
    });

    test('Dio 409 → "Conflict — try again"', () {
      expect(
        explainBulkError(_dio(409), BulkOperation.archive),
        'Conflict — try again',
      );
    });

    test('Unknown error → "Unknown error" fallback', () {
      expect(
        explainBulkError(Exception('boom'), BulkOperation.archive),
        'Unknown error',
      );
    });

    test('Dio 500 with no mapped status → "Unknown error" fallback', () {
      expect(
        explainBulkError(_dio(500), BulkOperation.archive),
        'Unknown error',
      );
    });
  });

  group('runBulkOperations', () {
    test('all success — every result is success with name preserved',
        () async {
      final results = await runBulkOperations<String>(
        items: const ['a', 'b', 'c'],
        operation: (_) async {},
        nameOf: (t) => 'name-$t',
        bulkOp: BulkOperation.addToMeal,
      );
      expect(results.length, 3);
      expect(results.every((r) => r.success), isTrue);
      expect(results.map((r) => r.targetName),
          ['name-a', 'name-b', 'name-c']);
    });

    test('partial failure — Future.wait does NOT abort on first throw',
        () async {
      final results = await runBulkOperations<String>(
        items: const ['a', 'b', 'c'],
        operation: (t) async {
          if (t == 'b') throw _dio(403);
        },
        nameOf: (t) => t,
        bulkOp: BulkOperation.addToMeal,
      );
      expect(results.length, 3);
      expect(results[0].success, isTrue);
      expect(results[1].success, isFalse);
      expect(results[1].errorReason, "You can't edit this recipe");
      expect(results[2].success, isTrue);
    });

    test('all failure — per-item reasons from explainBulkError', () async {
      final results = await runBulkOperations<String>(
        items: const ['a', 'b'],
        operation: (_) async => throw MealComponentDuplicateException(),
        nameOf: (t) => 'meal-$t',
        bulkOp: BulkOperation.addToMeal,
      );
      expect(results.every((r) => !r.success), isTrue);
      expect(
        results.every((r) => r.errorReason == 'Already in this Meal'),
        isTrue,
      );
    });

    test('empty input yields empty results list', () async {
      final results = await runBulkOperations<String>(
        items: const <String>[],
        operation: (_) async {},
        nameOf: (t) => t,
        bulkOp: BulkOperation.archive,
      );
      expect(results, isEmpty);
    });
  });
}
