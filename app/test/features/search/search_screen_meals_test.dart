// md-5: Search results include Meals with component-match disclosure.

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/features/search/search_screen.dart';
import 'package:palateful/features/search/widgets/meal_search_tile.dart';

Response<dynamic> _fakeResponse(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _SearchCapture {
  String? lastScope;
}

class _FakeApiClient extends ApiClient {
  final List<dynamic> myRecipes;
  final List<dynamic> myMeals;
  final _SearchCapture capture;

  _FakeApiClient({
    this.myRecipes = const [],
    this.myMeals = const [],
    _SearchCapture? capture,
  }) : capture = capture ?? _SearchCapture();

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
    capture.lastScope = scope;
    return _fakeResponse({
      'query': query,
      'my_recipes': myRecipes,
      'public_recipes': <Map<String, dynamic>>[],
      'my_meals': myMeals,
      'users': <Map<String, dynamic>>[],
    });
  }
}

void _registerFakes(_FakeApiClient client) {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  gi.registerSingleton<ApiClient>(client);
  if (gi.isRegistered<AuthService>()) gi.unregister<AuthService>();
  gi.registerSingleton<AuthService>(AuthService());
}

void _unregister() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  if (gi.isRegistered<AuthService>()) gi.unregister<AuthService>();
}

Map<String, dynamic> _mealHit({
  required String id,
  required String name,
  String? bookName,
  int componentCount = 2,
  Map<String, dynamic>? matched,
}) =>
    {
      'id': id,
      'name': name,
      'recipe_book_id': 'book-1',
      'recipe_book_name': bookName ?? 'Dinners',
      'component_count': componentCount,
      'top_component_image_urls': <String>[],
      'matched_component': matched,
    };

Future<void> _performSearch(WidgetTester tester, String query) async {
  tester.view.physicalSize = const Size(1080, 2400);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(() {
    tester.view.resetPhysicalSize();
    tester.view.resetDevicePixelRatio();
  });
  await tester.pumpWidget(const MaterialApp(home: SearchScreen()));
  await tester.enterText(find.byType(TextField), query);
  // The search controller debounces 300ms; wait past that.
  await tester.pump(const Duration(milliseconds: 350));
  await tester.pumpAndSettle();
}

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  tearDown(_unregister);

  group('SearchScreen — md-5 Meals', () {
    testWidgets('sends scope=recipes,meals on the wire', (tester) async {
      final capture = _SearchCapture();
      _registerFakes(_FakeApiClient(capture: capture));
      await _performSearch(tester, 'dressing');
      expect(capture.lastScope, equals('recipes,meals'));
    });

    testWidgets('zero-Meal response does not render My Meals section',
        (tester) async {
      _registerFakes(_FakeApiClient());
      await _performSearch(tester, 'pasta');
      expect(find.text('MY MEALS'), findsNothing);
      expect(find.byType(MealSearchTile), findsNothing);
    });

    testWidgets('direct-match Meal renders without Matches: subtitle',
        (tester) async {
      _registerFakes(_FakeApiClient(
        myMeals: [
          _mealHit(id: 'm1', name: 'Kale Salad Meal', matched: null),
        ],
      ));
      await _performSearch(tester, 'Kale');
      expect(find.byType(MealSearchTile), findsOneWidget);
      expect(find.text('Kale Salad Meal'), findsOneWidget);
      expect(find.textContaining('Matches:'), findsNothing);
    });

    testWidgets('component-match Meal renders Matches: subtitle',
        (tester) async {
      _registerFakes(_FakeApiClient(
        myMeals: [
          _mealHit(
            id: 'm1',
            name: 'Kale Salad Meal',
            matched: {'recipe_id': 'r1', 'name': 'Lemon Dressing'},
          ),
        ],
      ));
      await _performSearch(tester, 'dressing');
      expect(find.text('Matches: Lemon Dressing'), findsOneWidget);
    });

    testWidgets('My Meals section header renders between My and Public',
        (tester) async {
      _registerFakes(_FakeApiClient(
        myRecipes: [
          {
            'id': 'r1',
            'name': 'Pasta',
            'recipe_book_name': 'Dinners',
            'recipe_book_id': 'book-1',
            'tags': <String>[],
          },
        ],
        myMeals: [_mealHit(id: 'm1', name: 'Kale Salad Meal')],
      ));
      await _performSearch(tester, 'kale');
      expect(find.text('MY RECIPES'), findsOneWidget);
      expect(find.text('MY MEALS'), findsOneWidget);
    });
  });
}
