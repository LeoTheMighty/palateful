import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/meals/widgets/recipe_multiselect_picker.dart';

Response<dynamic> _ok(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _FakeApi extends ApiClient {
  Map<String, dynamic>? lastSearchArgs;
  String? lastBookId;

  Response<dynamic> getRecipesResponse = _ok({'recipes': <dynamic>[]});
  Response<dynamic> searchResponse = _ok({'my_recipes': <dynamic>[]});

  @override
  Future<Response<dynamic>> getRecipes(
    String bookId, {
    int limit = 20,
    int offset = 0,
    String? search,
  }) async {
    lastBookId = bookId;
    return getRecipesResponse;
  }

  @override
  Future<Response<dynamic>> search(
    String query, {
    int limit = 20,
    String? bookId,
    List<String>? tags,
    int? maxPrepTime,
    int? maxCookTime,
    String? scope,
  }) async {
    lastSearchArgs = {
      'q': query,
      'scope': scope,
      'limit': limit,
    };
    return searchResponse;
  }
}

Future<void> _openPicker(
  WidgetTester tester, {
  Set<String> alreadySelected = const {},
  Set<String> initiallyPicked = const {},
}) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: Builder(
          builder: (ctx) => ElevatedButton(
            onPressed: () async {
              await RecipeMultiselectPicker.show(
                ctx,
                bookId: 'book-1',
                bookName: 'Dinners',
                alreadySelectedIds: alreadySelected,
                initiallyPickedIds: initiallyPicked,
              );
            },
            child: const Text('Open'),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('Open'));
  // Wait for the sheet's slide animation + initial fetch to complete.
  await tester.pumpAndSettle();
}

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  late _FakeApi fakeApi;

  setUp(() {
    fakeApi = _FakeApi();
    final g = GetIt.instance;
    if (g.isRegistered<ApiClient>()) g.unregister<ApiClient>();
    g.registerSingleton<ApiClient>(fakeApi);
  });

  tearDown(() {
    final g = GetIt.instance;
    if (g.isRegistered<ApiClient>()) g.unregister<ApiClient>();
  });

  testWidgets('renders book-scoped list on open', (tester) async {
    fakeApi.getRecipesResponse = _ok({
      'recipes': [
        {'id': 'r1', 'name': 'Kale Salad'},
        {'id': 'r2', 'name': 'Lemon Dressing'},
      ],
    });

    await _openPicker(tester);

    expect(fakeApi.lastBookId, 'book-1');
    expect(find.text('Kale Salad'), findsOneWidget);
    expect(find.text('Lemon Dressing'), findsOneWidget);
  });

  testWidgets('typing switches to global search', (tester) async {
    fakeApi.getRecipesResponse = _ok({'recipes': <dynamic>[]});
    fakeApi.searchResponse = _ok({
      'my_recipes': [
        {
          'id': 'r9',
          'name': 'Pasta Carbonara',
          'recipe_book_id': 'b-other',
          'recipe_book_name': 'Italian',
        },
      ],
    });

    await _openPicker(tester);

    await tester.enterText(find.byType(TextField), 'past');
    // Debounce 250ms + buffer.
    await tester.pump(const Duration(milliseconds: 350));
    await tester.pump(const Duration(milliseconds: 50));

    expect(fakeApi.lastSearchArgs?['q'], 'past');
    expect(fakeApi.lastSearchArgs?['scope'], 'recipes');
    expect(find.text('Pasta Carbonara'), findsOneWidget);
    // Book-of-origin subtitle shown on cross-book hits.
    expect(find.text('Italian'), findsOneWidget);
  });

  testWidgets('tap row toggles selection', (tester) async {
    fakeApi.getRecipesResponse = _ok({
      'recipes': [
        {'id': 'r1', 'name': 'Kale Salad'},
      ],
    });

    await _openPicker(tester);

    // Initially unchecked.
    expect(find.byIcon(Icons.radio_button_unchecked), findsOneWidget);
    expect(find.byIcon(Icons.check_circle), findsNothing);

    await tester.tap(find.text('Kale Salad'));
    await tester.pump();

    expect(find.byIcon(Icons.check_circle), findsOneWidget);

    // Tap again — deselect.
    await tester.tap(find.text('Kale Salad'));
    await tester.pump();

    expect(find.byIcon(Icons.radio_button_unchecked), findsOneWidget);
    expect(find.byIcon(Icons.check_circle), findsNothing);
  });

  testWidgets('Done returns selected PickedRecipe list', (tester) async {
    fakeApi.getRecipesResponse = _ok({
      'recipes': [
        {'id': 'r1', 'name': 'Kale Salad'},
        {'id': 'r2', 'name': 'Lemon Dressing'},
      ],
    });

    final completer = Completer<List<PickedRecipe>>();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (ctx) => ElevatedButton(
              onPressed: () async {
                final result = await RecipeMultiselectPicker.show(
                  ctx,
                  bookId: 'book-1',
                  bookName: 'Dinners',
                );
                completer.complete(result);
              },
              child: const Text('Open'),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Open'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Kale Salad'));
    await tester.pump();
    await tester.tap(find.text('Lemon Dressing'));
    await tester.pump();

    await tester.tap(find.widgetWithText(FilledButton, 'Done'));
    await tester.pumpAndSettle();

    final picked = await completer.future;
    expect(picked.length, 2);
    expect(picked.map((p) => p.id).toSet(), {'r1', 'r2'});
  });

  testWidgets('alreadySelectedIds renders "Added" badge and blocks tap',
      (tester) async {
    fakeApi.getRecipesResponse = _ok({
      'recipes': [
        {'id': 'r1', 'name': 'Kale Salad'},
        {'id': 'r2', 'name': 'Lemon Dressing'},
      ],
    });

    await _openPicker(tester, alreadySelected: {'r1'});

    expect(find.text('Added'), findsOneWidget);

    // Tapping the already-added row should NOT mark it as picked.
    await tester.tap(find.text('Kale Salad'));
    await tester.pump();

    // The Done button should remain disabled (no picks).
    final done = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Done'),
    );
    expect(done.onPressed, isNull);
  });

}
