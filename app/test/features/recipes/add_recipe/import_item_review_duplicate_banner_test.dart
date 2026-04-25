import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/recipes/add_recipe/import_item_review_screen.dart';

/// import-dup-4 — screen-level regression sweep covering the
/// duplicate-banner integration in `ImportItemReviewScreen`.
///
/// The banner widget itself has 12 unit-level tests in
/// `duplicate_banner_test.dart`; this file exercises the screen-level
/// glue: parsing the response shape, rendering / hiding the banner,
/// and the no-duplicate regression path.

Response<dynamic> _ok(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

/// Stub ApiClient that captures the in-flight calls + returns a
/// caller-configured payload for `getImportItem`. Other methods
/// the screen touches are no-op'd so the screen doesn't crash.
class _StubApiClient extends ApiClient {
  _StubApiClient({required this.getResponse});

  Map<String, dynamic> getResponse;
  int skipCallCount = 0;
  int restoreCallCount = 0;
  String? lastSkippedItemId;
  String? lastRestoredRecipeId;

  @override
  Future<Response> getImportItem(
    String itemId, {
    bool includeParsedRecipe = false,
  }) async =>
      _ok(getResponse);

  @override
  Future<Response> skipImportItem(String itemId) async {
    skipCallCount++;
    lastSkippedItemId = itemId;
    return _ok({'id': itemId, 'status': 'skipped'});
  }

  @override
  Future<Response> restoreRecipe(String recipeId) async {
    restoreCallCount++;
    lastRestoredRecipeId = recipeId;
    return _ok({'id': recipeId});
  }

  @override
  Future<Response> updateImportItem(
    String itemId,
    Map<String, dynamic> userEdits,
  ) async =>
      _ok({'id': itemId});
}

Map<String, dynamic> _baseItem({
  Map<String, dynamic>? duplicate,
}) {
  return {
    'id': 'item-1',
    'status': 'awaiting_review',
    'source_type': 'url',
    'source_url': 'https://example.com/r',
    'raw_data': const <String, dynamic>{},
    'parsed_recipe': const {
      'name': "Mom's Brisket",
      'description': 'A classic',
      'ingredients': <dynamic>[],
      'steps': <dynamic>[],
    },
    'user_edits': null,
    'error_message': null,
    'error_code': null,
    'retry_count': 0,
    'ai_cost_cents': 0,
    'import_job_id': 'job-1',
    'created_recipe_id': null,
    'created_at': '2026-04-25T10:00:00Z',
    'updated_at': '2026-04-25T10:00:00Z',
    'last_successful_stage': 'extracted',
    'last_retry_at': null,
    'awaiting_review_reason': null,
    'inferred_fields': const <String>[],
    'duplicate': duplicate,
  };
}

void main() {
  late _StubApiClient stub;

  setUp(() {
    final gi = GetIt.instance;
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
    stub = _StubApiClient(getResponse: _baseItem(duplicate: null));
    gi.registerSingleton<ApiClient>(stub);
  });

  tearDown(() {
    final gi = GetIt.instance;
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  });

  /// Build a router whose `/` lands on a placeholder Home, then we
  /// push the review screen so `context.pop` has something to pop to.
  /// Without the pre-push the screen's pop-on-success calls error
  /// with "There is nothing to pop".
  GoRouter _router(String itemId) {
    return GoRouter(
      initialLocation: '/',
      routes: [
        GoRoute(
          path: '/',
          builder: (_, _) => const Scaffold(body: Text('HOME')),
        ),
        GoRoute(
          path: '/review/:id',
          builder: (_, state) => ImportItemReviewScreen(
            itemId: state.pathParameters['id']!,
          ),
        ),
        GoRoute(
          path: '/recipes/:id',
          builder: (_, state) =>
              Scaffold(body: Text('RECIPE-${state.pathParameters['id']}')),
        ),
      ],
    );
  }

  Future<void> _pumpReview(
    WidgetTester tester, {
    String itemId = 'item-1',
  }) async {
    final router = _router(itemId);
    await tester.pumpWidget(MaterialApp.router(routerConfig: router));
    // Land on home, then push the review screen so pop() works.
    router.push('/review/$itemId');
    await tester.pumpAndSettle();
  }

  testWidgets(
      'no-duplicate response → form renders normally, no banner (regression)',
      (tester) async {
    // duplicate is omitted entirely (older server / null path).
    stub.getResponse = _baseItem(duplicate: null);

    await _pumpReview(tester);
    // pumpAndSettle already done in _pumpReview

    expect(find.byKey(const Key('duplicate_banner')), findsNothing);
    // Standard form is up — recipe name field present.
    expect(find.text('Recipe Name'), findsOneWidget);
  });

  testWidgets('empty duplicate.matches → no banner', (tester) async {
    stub.getResponse = _baseItem(duplicate: const {'matches': <dynamic>[]});

    await _pumpReview(tester);
    // pumpAndSettle already done in _pumpReview

    expect(find.byKey(const Key('duplicate_banner')), findsNothing);
  });

  testWidgets('active match → blue banner with Skip + Add anyway',
      (tester) async {
    stub.getResponse = _baseItem(duplicate: const {
      'matches': [
        {
          'recipe_id': 'r-1',
          'title': "Mom's Brisket",
          'current_book_id': 'b-1',
          'current_book_name': "Mom's Recipes",
          'archived_at': null,
          'last_cooked': null,
          'match_kind': 'title',
        }
      ],
    });

    await _pumpReview(tester);
    // pumpAndSettle already done in _pumpReview

    expect(find.byKey(const Key('duplicate_banner')), findsOneWidget);
    expect(find.byKey(const Key('duplicate_banner_skip')), findsOneWidget);
    expect(
      find.byKey(const Key('duplicate_banner_add_anyway')),
      findsOneWidget,
    );
    expect(find.byKey(const Key('duplicate_banner_restore')), findsNothing);
  });

  testWidgets('archived match → amber banner with Restore button',
      (tester) async {
    stub.getResponse = _baseItem(duplicate: const {
      'matches': [
        {
          'recipe_id': 'r-archived',
          'title': "Mom's Brisket",
          'current_book_id': 'b-1',
          'current_book_name': "Mom's Recipes",
          'archived_at': '2024-03-12T09:30:00+00:00',
          'last_cooked': null,
          'match_kind': 'title',
        }
      ],
    });

    await _pumpReview(tester);
    // pumpAndSettle already done in _pumpReview

    expect(find.byKey(const Key('duplicate_banner_restore')), findsOneWidget);
    expect(find.textContaining('You archived'), findsOneWidget);
  });

  testWidgets('Add anyway hides banner but keeps form usable', (tester) async {
    stub.getResponse = _baseItem(duplicate: const {
      'matches': [
        {
          'recipe_id': 'r-1',
          'title': "Mom's Brisket",
          'current_book_id': 'b-1',
          'current_book_name': "Mom's Recipes",
          'archived_at': null,
          'last_cooked': null,
          'match_kind': 'title',
        }
      ],
    });

    await _pumpReview(tester);
    // pumpAndSettle already done in _pumpReview

    expect(find.byKey(const Key('duplicate_banner')), findsOneWidget);

    await tester.tap(find.byKey(const Key('duplicate_banner_add_anyway')));
    await tester.pumpAndSettle();

    // Banner gone; form still rendered.
    expect(find.byKey(const Key('duplicate_banner')), findsNothing);
    expect(find.text('Recipe Name'), findsOneWidget);
    // No backend mutation fired.
    expect(stub.skipCallCount, 0);
    expect(stub.restoreCallCount, 0);
  });

  testWidgets('Skip on banner calls skipImportItem and pops', (tester) async {
    stub.getResponse = _baseItem(duplicate: const {
      'matches': [
        {
          'recipe_id': 'r-1',
          'title': "Mom's Brisket",
          'current_book_id': 'b-1',
          'current_book_name': "Mom's Recipes",
          'archived_at': null,
          'last_cooked': null,
          'match_kind': 'title',
        }
      ],
    });

    await _pumpReview(tester);
    // pumpAndSettle already done in _pumpReview

    await tester.tap(find.byKey(const Key('duplicate_banner_skip')));
    await tester.pumpAndSettle();

    expect(stub.skipCallCount, 1);
    expect(stub.lastSkippedItemId, 'item-1');
  });

  testWidgets(
      'Restore on archived banner calls restoreRecipe THEN skipImportItem',
      (tester) async {
    stub.getResponse = _baseItem(duplicate: const {
      'matches': [
        {
          'recipe_id': 'r-archived',
          'title': "Mom's Brisket",
          'current_book_id': 'b-1',
          'current_book_name': "Mom's Recipes",
          'archived_at': '2024-03-12T09:30:00+00:00',
          'last_cooked': null,
          'match_kind': 'title',
        }
      ],
    });

    await _pumpReview(tester);
    // pumpAndSettle already done in _pumpReview

    await tester.tap(find.byKey(const Key('duplicate_banner_restore')));
    await tester.pumpAndSettle();

    expect(stub.restoreCallCount, 1);
    expect(stub.lastRestoredRecipeId, 'r-archived');
    expect(stub.skipCallCount, 1);
    expect(stub.lastSkippedItemId, 'item-1');
  });

  testWidgets(
      'multi-match shows "+N more" affordance and bottom sheet on tap',
      (tester) async {
    stub.getResponse = _baseItem(duplicate: const {
      'matches': [
        {
          'recipe_id': 'r-1',
          'title': "Mom's Brisket",
          'current_book_id': 'b-1',
          'current_book_name': "Mom's Recipes",
          'archived_at': null,
          'last_cooked': null,
          'match_kind': 'title',
        },
        {
          'recipe_id': 'r-2',
          'title': "Mom's Brisket",
          'current_book_id': 'b-2',
          'current_book_name': 'Other Book',
          'archived_at': null,
          'last_cooked': null,
          'match_kind': 'title',
        },
      ],
    });

    await _pumpReview(tester);
    // pumpAndSettle already done in _pumpReview

    expect(
      find.byKey(const Key('duplicate_banner_show_all')),
      findsOneWidget,
    );
    expect(
      find.textContaining('+ 1 more match — show all'),
      findsOneWidget,
    );

    await tester.tap(find.byKey(const Key('duplicate_banner_show_all')));
    await tester.pumpAndSettle();

    // Bottom sheet rendered with both matches as ListTiles.
    expect(find.text('Other Book'), findsOneWidget);
  });
}
