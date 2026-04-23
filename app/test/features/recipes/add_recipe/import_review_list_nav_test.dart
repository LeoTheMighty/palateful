import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/recipes/add_recipe/import_review_list_screen.dart';

Response<dynamic> _fakeResponse(dynamic data) {
  return Response(
    data: data,
    requestOptions: RequestOptions(path: ''),
    statusCode: 200,
  );
}

/// Stub ApiClient that returns an empty items list so ImportReviewListScreen
/// exits its loading state quickly. Nothing about nav depends on payload.
class _StubApiClient extends ApiClient {
  @override
  Future<Response> listImportItems(
    String jobId, {
    String? status,
    bool includeArchived = false,
  }) async =>
      _fakeResponse({'items': []});

  @override
  Future<Response> listImportItemsBatch(
    List<String> jobIds, {
    String? status,
    bool includeArchived = false,
  }) async =>
      _fakeResponse({'items': []});
}

void _registerFakes() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  gi.registerSingleton<ApiClient>(_StubApiClient());
}

void _unregister() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
}

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });
  setUp(_registerFakes);
  tearDown(_unregister);

  group('ImportReviewListScreen — terminal nav', () {
    testWidgets('back button pops to previous GoRouter location when warm',
        (tester) async {
      // Warm launch: home → book detail → review-list. Pop from review-list
      // should land back on book detail (GoRouter's internal stack handles
      // pushReplacement entry points transparently).
      final router = GoRouter(
        initialLocation: '/',
        routes: [
          GoRoute(
            path: '/',
            builder: (_, _) =>
                const Scaffold(body: Text('HOME')),
          ),
          GoRoute(
            path: '/book/:id',
            builder: (_, state) => Scaffold(
              body: Text('BOOK-${state.pathParameters['id']}'),
            ),
          ),
          GoRoute(
            path: '/review-list/:jobId',
            builder: (_, state) => ImportReviewListScreen(
              jobId: state.pathParameters['jobId']!,
            ),
          ),
        ],
      );

      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      await tester.pumpAndSettle();

      router.push('/book/42');
      await tester.pumpAndSettle();
      router.push('/review-list/job-1');
      await tester.pumpAndSettle();

      expect(find.text('Review Imports'), findsOneWidget);

      await tester.tap(find.byIcon(Icons.arrow_back));
      await tester.pumpAndSettle();

      // Warm: back to book detail (not home).
      expect(find.text('BOOK-42'), findsOneWidget);
      expect(find.text('Review Imports'), findsNothing);
    });

    testWidgets('back button goes to / when stack cannot pop (cold launch)',
        (tester) async {
      // Cold launch: router initial location is review-list directly.
      final router = GoRouter(
        initialLocation: '/review-list/job-cold',
        routes: [
          GoRoute(
            path: '/',
            builder: (_, _) =>
                const Scaffold(body: Text('HOME')),
          ),
          GoRoute(
            path: '/review-list/:jobId',
            builder: (_, state) => ImportReviewListScreen(
              jobId: state.pathParameters['jobId']!,
            ),
          ),
        ],
      );

      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      await tester.pumpAndSettle();

      expect(find.text('Review Imports'), findsOneWidget);

      await tester.tap(find.byIcon(Icons.arrow_back));
      await tester.pumpAndSettle();

      expect(find.text('HOME'), findsOneWidget);
    });

    testWidgets('PopScope with canPop:false wraps the scaffold',
        (tester) async {
      // Hardware back is hard to fire cleanly in widget tests, so we just
      // assert that the screen is wrapped in a PopScope configured to
      // intercept (canPop:false). The pop handler fires the same
      // _popOrHome helper that the two tests above verify.
      final router = GoRouter(
        initialLocation: '/review-list/job-1',
        routes: [
          GoRoute(
            path: '/review-list/:jobId',
            builder: (_, state) => ImportReviewListScreen(
              jobId: state.pathParameters['jobId']!,
            ),
          ),
        ],
      );

      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      await tester.pumpAndSettle();

      final matching = find.byWidgetPredicate(
        (w) => w is PopScope && w.canPop == false,
      );
      expect(matching, findsOneWidget);

      final popScope = tester.widget<PopScope>(matching);
      expect(popScope.onPopInvokedWithResult, isNotNull);
    });
  });
}
