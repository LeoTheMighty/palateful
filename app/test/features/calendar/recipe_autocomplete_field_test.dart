import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/calendar/widgets/recipe_autocomplete_field.dart';

Response<dynamic> _fakeResp(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _FakeApiClient extends ApiClient {
  final List<Map<String, dynamic>> recipes;
  final bool throwTimeout;
  final List<Map<String, dynamic>> searchCalls = [];

  _FakeApiClient({this.recipes = const [], this.throwTimeout = false});

  @override
  Future<Response> search(
    String query, {
    int limit = 20,
    String? bookId,
    List<String>? tags,
    int? maxPrepTime,
    int? maxCookTime,
    String? scope,
  }) async {
    searchCalls.add({'q': query, 'scope': scope, 'limit': limit});
    if (throwTimeout) {
      throw TimeoutException('test-induced timeout');
    }
    return _fakeResp({
      'my_recipes': recipes,
      'public_recipes': [],
      'users': [],
    });
  }
}

Widget _host(Widget child) => MaterialApp(home: Scaffold(body: child));

void main() {
  setUpAll(() async {
  });

  testWidgets('recent chips render on empty input', (tester) async {
    final ctrl = TextEditingController();
    await tester.pumpWidget(_host(RecipeAutocompleteField(
      controller: ctrl,
      recentMeals: const ['Leftovers', 'Takeout'],
      onPicked: (_) {},
      apiClient: _FakeApiClient(),
    )));
    await tester.pump();

    expect(find.text('Leftovers'), findsOneWidget);
    expect(find.text('Takeout'), findsOneWidget);
  });

  testWidgets('typing a query fires search with scope=recipes',
      (tester) async {
    final ctrl = TextEditingController();
    final api = _FakeApiClient(recipes: [
      {
        'id': 'r-1',
        'name': 'Pasta carbonara',
        'recipe_book_name': 'Weeknight',
      },
    ]);

    await tester.pumpWidget(_host(RecipeAutocompleteField(
      controller: ctrl,
      recentMeals: const [],
      onPicked: (_) {},
      apiClient: api,
      debounce: const Duration(milliseconds: 10),
    )));
    await tester.pump();

    ctrl.text = 'pasta';
    await tester.pump(const Duration(milliseconds: 20)); // past debounce
    await tester.pumpAndSettle(const Duration(milliseconds: 100));

    expect(api.searchCalls, hasLength(1));
    expect(api.searchCalls.first['scope'], 'recipes');
    expect(api.searchCalls.first['q'], 'pasta');
    expect(find.text('Pasta carbonara'), findsOneWidget);
  });

  testWidgets('no-match surfaces the free-text fallback row', (tester) async {
    final ctrl = TextEditingController();
    PickedMeal? picked;

    await tester.pumpWidget(_host(RecipeAutocompleteField(
      controller: ctrl,
      recentMeals: const [],
      onPicked: (p) => picked = p,
      apiClient: _FakeApiClient(),
      debounce: const Duration(milliseconds: 10),
    )));
    await tester.pump();

    ctrl.text = 'zzzz';
    await tester.pump(const Duration(milliseconds: 20));
    await tester.pumpAndSettle();

    expect(find.textContaining("Save 'zzzz' as free-text meal"), findsOneWidget);

    await tester.tap(find.textContaining("Save 'zzzz'"));
    await tester.pumpAndSettle();
    expect(picked, isNotNull);
    expect(picked!.isFreeText, isTrue);
    expect(picked!.title, 'zzzz');
  });

  testWidgets('tapping a match picks the recipe and shows Linked chip',
      (tester) async {
    final ctrl = TextEditingController();
    PickedMeal? picked;
    final api = _FakeApiClient(recipes: [
      {
        'id': 'r-9',
        'name': 'Chili',
        'recipe_book_name': 'Favorites',
      },
    ]);

    await tester.pumpWidget(_host(RecipeAutocompleteField(
      controller: ctrl,
      recentMeals: const [],
      onPicked: (p) => picked = p,
      apiClient: api,
      debounce: const Duration(milliseconds: 10),
    )));
    await tester.pump();
    ctrl.text = 'chili';
    await tester.pump(const Duration(milliseconds: 20));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Chili'));
    await tester.pumpAndSettle();

    expect(picked, isNotNull);
    expect(picked!.isFreeText, isFalse);
    expect(picked!.recipeId, 'r-9');
    expect(find.text('Linked to Chili'), findsOneWidget);
    expect(ctrl.text, 'Chili');
  });

  testWidgets('network timeout falls back to recent-meals matches',
      (tester) async {
    final ctrl = TextEditingController();
    final api = _FakeApiClient(throwTimeout: true);

    await tester.pumpWidget(_host(RecipeAutocompleteField(
      controller: ctrl,
      recentMeals: const ['Pasta Tuesday', 'Chicken curry'],
      onPicked: (_) {},
      apiClient: api,
      debounce: const Duration(milliseconds: 10),
    )));
    await tester.pump();

    ctrl.text = 'pasta';
    await tester.pump(const Duration(milliseconds: 20));
    await tester.pumpAndSettle();

    // The falling-back recent meal must surface; the other one ("Chicken curry")
    // does not match the query and is filtered out.
    expect(find.text('Pasta Tuesday'), findsOneWidget);
    expect(find.text('Chicken curry'), findsNothing);
  });
}
