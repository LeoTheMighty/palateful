import 'package:dio/dio.dart';

import '../../meals/services/meal_service.dart';

/// Which bulk surface invoked the dispatcher. Drives user-facing error
/// strings in [explainBulkError] + the partial-failure dialog title.
enum BulkOperation { addToMeal, archive }

/// One per-item outcome of a bulk dispatch. The partial-failure dialog
/// renders one row per `success == false` entry; successful rows are
/// never shown but are retained so callers can compute "X of Y" copy.
class BulkOperationResult {
  final String targetName;
  final bool success;
  final String? errorReason;

  const BulkOperationResult({
    required this.targetName,
    required this.success,
    this.errorReason,
  });
}

/// Map an exception thrown from an Add-to-Meal or Archive dispatch to a
/// one-line, user-facing reason. Kept out of the widget layer so the
/// copy is unit-testable and shared between the snackbar + dialog.
String explainBulkError(Object error, BulkOperation op) {
  if (error is MealComponentDuplicateException) {
    return 'Already in this Meal';
  }
  if (error is MealComponentUnavailableException) {
    return 'Recipe is no longer available';
  }
  if (error is DioException) {
    switch (error.response?.statusCode) {
      case 403:
        return op == BulkOperation.archive
            ? "You can't archive this"
            : "You can't edit this recipe";
      case 404:
        return 'No longer available';
      case 409:
        return 'Conflict — try again';
    }
  }
  return 'Unknown error';
}

/// Run a list of per-item operations in parallel, collecting a
/// [BulkOperationResult] per item without aborting on the first failure.
///
/// Each future is wrapped in its own try/catch so `Future.wait` cannot
/// reject — the returned list always has one row per input item, in
/// the same order.
Future<List<BulkOperationResult>> runBulkOperations<T>({
  required List<T> items,
  required Future<void> Function(T item) operation,
  required String Function(T item) nameOf,
  required BulkOperation bulkOp,
}) async {
  final futures = items.map((item) async {
    try {
      await operation(item);
      return BulkOperationResult(
        targetName: nameOf(item),
        success: true,
      );
    } catch (e) {
      return BulkOperationResult(
        targetName: nameOf(item),
        success: false,
        errorReason: explainBulkError(e, bulkOp),
      );
    }
  });
  return Future.wait(futures);
}
