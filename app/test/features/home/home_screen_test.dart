import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/home/home_screen.dart';
import 'package:palateful/features/recipes/add_recipe/batch_parser_service.dart';

Response<dynamic> _fakeResponse(dynamic data) {
  return Response(
    data: data,
    requestOptions: RequestOptions(path: ''),
    statusCode: 200,
  );
}

/// Minimal fake that overrides only the methods called by HomeScreen.
class _FakeApiClient extends ApiClient {
  final Map<String, dynamic>? todayMealEvent;

  _FakeApiClient({this.todayMealEvent});

  @override
  Future<Response> getRecipeBooks({int limit = 20, int offset = 0}) async =>
      _fakeResponse({'items': []});

  @override
  Future<Response> getFavorites() async => _fakeResponse({'items': []});

  @override
  Future<Response> getMealEventsForToday() async {
    if (todayMealEvent != null) {
      return _fakeResponse({
        'items': [todayMealEvent],
        'total': 1,
      });
    }
    return _fakeResponse({'items': [], 'total': 0});
  }

  @override
  Future<Response> getRecentlyCookedRecipes({int limit = 5}) async =>
      _fakeResponse({'items': [], 'total': 0});
}

void _registerFakes(_FakeApiClient client) {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  gi.registerSingleton<ApiClient>(client);
  if (gi.isRegistered<BatchParserService>()) gi.unregister<BatchParserService>();
  gi.registerLazySingleton<BatchParserService>(() => BatchParserService());
}

void _unregister() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  if (gi.isRegistered<BatchParserService>()) gi.unregister<BatchParserService>();
}

void main() {
  setUpAll(() async {
    // Initialize dotenv with an empty map so ApiClient constructor can read env vars
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  tearDown(_unregister);

  group('HomeScreen — hero card', () {
    testWidgets('shows timing chip when meal event has prep and cook time',
        (tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      _registerFakes(_FakeApiClient(
        todayMealEvent: {
          'id': 'evt-1',
          'title': 'Test Dinner',
          'scheduled_at': DateTime.now().toIso8601String(),
          'meal_type': 'dinner',
          'status': 'planned',
          'is_shared': true,
          'owner_id': 'u1',
          'recipe': {
            'id': 'r1',
            'name': 'Pasta Carbonara',
            'image_url': null,
            'prep_time': 15,
            'cook_time': 20,
          },
        },
      ));

      await tester.pumpWidget(const MaterialApp(home: HomeScreen()));
      await tester.pump(); // Let async load complete

      expect(find.text('35 min'), findsOneWidget);
    });

    testWidgets('hides timing chip when meal event has no timing info',
        (tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      _registerFakes(_FakeApiClient(
        todayMealEvent: {
          'id': 'evt-1',
          'title': 'Test Dinner',
          'scheduled_at': DateTime.now().toIso8601String(),
          'meal_type': 'dinner',
          'status': 'planned',
          'is_shared': true,
          'owner_id': 'u1',
          'recipe': {
            'id': 'r1',
            'name': 'Pasta Carbonara',
            'image_url': null,
            'prep_time': null,
            'cook_time': null,
          },
        },
      ));

      await tester.pumpWidget(const MaterialApp(home: HomeScreen()));
      await tester.pump();

      expect(find.textContaining(RegExp(r'^\d+ min$')), findsNothing);
    });
  });
}
