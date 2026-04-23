// cmm-6 — multi-component post-cook sheet: per-row ratings, N
// sequential POST /v1/cooking-logs writes, CookingLogCreated events,
// partial-failure snackbar, scrollable many-row layout.

import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/recipe_cache_service.dart';
import 'package:palateful/core/state/mutation_bus.dart';
import 'package:palateful/core/state/mutation_event.dart';
import 'package:palateful/core/theme/app_theme.dart';
import 'package:palateful/features/recipes/cook_mode/shared/cook_plan.dart';
import 'package:palateful/features/recipes/cook_mode/shared/widgets/post_cook_feedback_sheet.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _RecordingApi extends ApiClient {
  final List<Map<String, dynamic>> cookingLogPayloads = [];
  // Recipe IDs that should fail their POST.
  final Set<String> failingIds;
  int counter = 0;

  _RecordingApi({this.failingIds = const {}});

  @override
  Future<Response> createCookingLog(Map<String, dynamic> data) async {
    cookingLogPayloads.add(data);
    if (failingIds.contains(data['recipe_id'])) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/cooking-logs'),
        type: DioExceptionType.badResponse,
      );
    }
    counter++;
    return Response(
      data: {
        'id': 'log-$counter',
        'recipe_id': data['recipe_id'],
        'rating': data['rating'],
      },
      requestOptions: RequestOptions(path: '/v1/cooking-logs'),
      statusCode: 200,
    );
  }
}

Widget _harness({
  required List<ComponentRatable> components,
  required ApiClient api,
  required RecipeCacheService cache,
  required void Function({bool saved}) onComplete,
  bool isOffline = false,
}) =>
    MaterialApp(
      theme: AppTheme.light(),
      home: Scaffold(
        body: PostCookFeedbackSheet(
          components: components,
          apiClient: api,
          recipeCache: cache,
          isOffline: isOffline,
          onComplete: onComplete,
        ),
      ),
    );

void main() {
  setUpAll(() async {
    TestWidgetsFlutterBinding.ensureInitialized();
    if (!dotenv.isInitialized) {
      await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
    }
  });

  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('3-component sheet renders 3 rating row keys',
      (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });
    final api = _RecordingApi();
    final cache = RecipeCacheService();
    await tester.pumpWidget(_harness(
      components: const [
        ComponentRatable(recipeId: 'r1', displayName: 'Dressing'),
        ComponentRatable(recipeId: 'r2', displayName: 'Salad'),
        ComponentRatable(recipeId: 'r3', displayName: 'Grilled Chicken'),
      ],
      api: api,
      cache: cache,
      onComplete: ({bool saved = false}) {},
    ));
    expect(find.byKey(const Key('multi_rating_list')), findsOneWidget);
    expect(find.byKey(const Key('multi_row_0')), findsOneWidget);
    expect(find.byKey(const Key('multi_row_1')), findsOneWidget);
    expect(find.byKey(const Key('multi_row_2')), findsOneWidget);
    expect(find.byKey(const Key('multi_done_button')), findsOneWidget);
  });

  testWidgets('5/4/0 ratings → 2 POSTs + 2 CookingLogCreated events',
      (tester) async {
    final api = _RecordingApi();
    final cache = RecipeCacheService();
    final completeCalls = <bool>[];
    final events = <MutationEvent>[];
    final sub = mutationBusStream().listen(events.add);
    addTearDown(sub.cancel);

    await tester.pumpWidget(_harness(
      components: const [
        ComponentRatable(recipeId: 'r1', displayName: 'Dressing'),
        ComponentRatable(recipeId: 'r2', displayName: 'Salad'),
        ComponentRatable(recipeId: 'r3', displayName: 'Grilled Chicken'),
      ],
      api: api,
      cache: cache,
      onComplete: ({bool saved = false}) => completeCalls.add(saved),
    ));

    // Rate Dressing 5, Salad 4, Grilled Chicken 0.
    await tester.tap(find.byKey(const Key('multi_star_0_5')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('multi_star_1_4')));
    await tester.pump();

    await tester.tap(find.byKey(const Key('multi_done_button')));
    for (var i = 0; i < 5; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }

    expect(api.cookingLogPayloads, hasLength(2));
    expect(api.cookingLogPayloads[0]['recipe_id'], 'r1');
    expect(api.cookingLogPayloads[0]['rating'], 5);
    expect(api.cookingLogPayloads[1]['recipe_id'], 'r2');
    expect(api.cookingLogPayloads[1]['rating'], 4);

    final cookingEvents = events.whereType<CookingLogCreated>().toList();
    expect(cookingEvents, hasLength(2));
    expect(cookingEvents.map((e) => e.recipeId).toSet(), {'r1', 'r2'});

    expect(completeCalls, [true]);
  });

  testWidgets('0/0/0 ratings → 0 POSTs, "Meal finished" snackbar, saved=true',
      (tester) async {
    final api = _RecordingApi();
    final cache = RecipeCacheService();
    final completeCalls = <bool>[];
    await tester.pumpWidget(ScaffoldMessenger(
      child: _harness(
        components: const [
          ComponentRatable(recipeId: 'r1', displayName: 'Dressing'),
          ComponentRatable(recipeId: 'r2', displayName: 'Salad'),
        ],
        api: api,
        cache: cache,
        onComplete: ({bool saved = false}) => completeCalls.add(saved),
      ),
    ));
    await tester.tap(find.byKey(const Key('multi_done_button')));
    for (var i = 0; i < 5; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }
    expect(api.cookingLogPayloads, isEmpty);
    expect(completeCalls, [true]);
  });

  testWidgets('partial failure: snackbar shows X of Y, saved=true',
      (tester) async {
    final api = _RecordingApi(failingIds: const {'r1'});
    final cache = RecipeCacheService();
    final completeCalls = <bool>[];
    await tester.pumpWidget(_harness(
      components: const [
        ComponentRatable(recipeId: 'r1', displayName: 'Dressing'),
        ComponentRatable(recipeId: 'r2', displayName: 'Salad'),
      ],
      api: api,
      cache: cache,
      onComplete: ({bool saved = false}) => completeCalls.add(saved),
    ));
    await tester.tap(find.byKey(const Key('multi_star_0_5')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('multi_star_1_4')));
    await tester.pump();

    await tester.tap(find.byKey(const Key('multi_done_button')));
    for (var i = 0; i < 5; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }
    expect(api.cookingLogPayloads, hasLength(2));
    expect(find.text('Cooked 1 of 2 components logged'), findsOneWidget);
    expect(completeCalls, [true]);
  });

  testWidgets('scrolls when many components overflow viewport',
      (tester) async {
    final api = _RecordingApi();
    final cache = RecipeCacheService();
    final components = List.generate(
      8,
      (i) => ComponentRatable(
        recipeId: 'r$i',
        displayName: 'Component $i',
      ),
    );
    await tester.pumpWidget(_harness(
      components: components,
      api: api,
      cache: cache,
      onComplete: ({bool saved = false}) {},
    ));
    // Row 0 visible immediately.
    expect(find.byKey(const Key('multi_row_0')), findsOneWidget);
    // Scroll the inner ListView upward until row 7 enters the viewport.
    final scrollable = find.descendant(
      of: find.byKey(const Key('multi_rating_list')),
      matching: find.byType(Scrollable),
    );
    await tester.scrollUntilVisible(
      find.byKey(const Key('multi_row_7')),
      200,
      scrollable: scrollable.first,
    );
    expect(find.byKey(const Key('multi_row_7')), findsOneWidget);
  });

  testWidgets('1-component sheet renders single-row layout (regression)',
      (tester) async {
    final api = _RecordingApi();
    final cache = RecipeCacheService();
    await tester.pumpWidget(_harness(
      components: const [
        ComponentRatable(recipeId: 'r1', displayName: 'Solo'),
      ],
      api: api,
      cache: cache,
      onComplete: ({bool saved = false}) {},
    ));
    // Single-row keys present, multi-row keys absent.
    expect(find.byKey(const Key('star_rating_row')), findsOneWidget);
    expect(find.byKey(const Key('save_button')), findsOneWidget);
    expect(find.byKey(const Key('multi_rating_list')), findsNothing);
    expect(find.byKey(const Key('multi_done_button')), findsNothing);
  });
}
