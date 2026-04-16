import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/recipes/add_recipe/models/import_batch.dart';
import 'package:palateful/features/recipes/add_recipe/state/import_batches_provider.dart';
import 'package:palateful/features/recipes/add_recipe/widgets/import_batches_strip.dart';

Response<dynamic> _fakeResponse(dynamic data) {
  return Response(
    data: data,
    requestOptions: RequestOptions(path: ''),
    statusCode: 200,
  );
}

/// Captures calls so we can assert them from tests.
class _SpyApiClient extends ApiClient {
  final List<String> retriedItemIds = [];
  final List<String> dismissedItemIds = [];
  final List<String> listedJobIds = [];
  List<Map<String, dynamic>> failedItemsToReturn = const [];

  @override
  Future<Response> retryImportItem(String itemId) async {
    retriedItemIds.add(itemId);
    return _fakeResponse({
      'item_id': itemId,
      'dispatched_task': 'extract_recipe_task',
      'resumed_from_stage': 'parsed',
      'status': 'extracting',
    });
  }

  @override
  Future<Response> dismissImportItem(String itemId) async {
    dismissedItemIds.add(itemId);
    return _fakeResponse({
      'item_id': itemId,
      'dismissed_at': DateTime.now().toIso8601String(),
      'job_dismissed': true,
    });
  }

  @override
  Future<Response> listImportItems(String jobId, {String? status}) async {
    listedJobIds.add(jobId);
    return _fakeResponse({'items': failedItemsToReturn});
  }

  @override
  Future<Response> listParserBatches(
      {bool activeOnly = true, int limit = 20}) async {
    return _fakeResponse({'batches': []});
  }
}

ImportBatch _failedBatch() {
  return ImportBatch(
    id: 'batch-1',
    status: 'failed',
    groupCount: 1,
    recipeBookId: null,
    createdAt: DateTime(2026, 4, 15, 12, 0),
    completedAt: DateTime(2026, 4, 15, 12, 5),
    errorMessage: 'OCR crashed mid-pipeline',
    jobs: const [],
    importJobs: const [ImportBatchImportJob(id: 'ij-1', status: 'failed')],
  );
}

void _registerFakes(_SpyApiClient client) {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  gi.registerSingleton<ApiClient>(client);
}

void _unregister() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
}

Widget _wrap(Widget child) {
  return ProviderScope(
    child: MaterialApp(
      home: Scaffold(body: child),
    ),
  );
}

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  tearDown(_unregister);

  group('ImportBatchesStrip — failed state', () {
    testWidgets('renders Retry and Dismiss buttons on failed batch',
        (tester) async {
      _registerFakes(_SpyApiClient());
      await tester.pumpWidget(_wrap(
        ImportBatchesStrip(
          state: ImportBatchesState(recentlyCompleted: [_failedBatch()]),
        ),
      ));

      expect(find.text('Failed'), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
      expect(find.text('Dismiss'), findsOneWidget);
    });

    testWidgets('tapping Retry fetches failed items and calls retry per item',
        (tester) async {
      final spy = _SpyApiClient()
        ..failedItemsToReturn = [
          {'id': 'item-1'},
          {'id': 'item-2'},
        ];
      _registerFakes(spy);

      await tester.pumpWidget(_wrap(
        ImportBatchesStrip(
          state: ImportBatchesState(recentlyCompleted: [_failedBatch()]),
        ),
      ));

      await tester.tap(find.text('Retry'));
      // Drain the async microtasks without calling pumpAndSettle — the
      // provider's internal poll timer never settles, so pumpAndSettle
      // would time out.
      for (var i = 0; i < 5; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }

      expect(spy.listedJobIds, ['ij-1']);
      expect(spy.retriedItemIds, ['item-1', 'item-2']);
    });

    testWidgets('tapping Dismiss calls dismissImportItem and shows snackbar',
        (tester) async {
      final spy = _SpyApiClient()
        ..failedItemsToReturn = [
          {'id': 'item-1'},
        ];
      _registerFakes(spy);

      await tester.pumpWidget(_wrap(
        ImportBatchesStrip(
          state: ImportBatchesState(recentlyCompleted: [_failedBatch()]),
        ),
      ));

      await tester.tap(find.text('Dismiss'));
      await tester.pump(); // Kick optimistic state + snackbar
      await tester.pump(const Duration(milliseconds: 50));

      // Snackbar should be visible with Undo action.
      expect(find.text('Import dismissed'), findsOneWidget);
      expect(find.text('Undo'), findsOneWidget);

      // Give the fire-and-forget backend call time to land.
      await tester.pump(const Duration(milliseconds: 100));
      expect(spy.dismissedItemIds, ['item-1']);
    });
  });
}
