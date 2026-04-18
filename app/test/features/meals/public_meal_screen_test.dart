import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/meals/models/meal.dart';
import 'package:palateful/features/meals/public_meal_screen.dart';
import 'package:palateful/features/meals/services/meal_service.dart';

class _FakeApi extends ApiClient {}

class _FakeMealService extends MealService {
  PublicMealDto? stubbedMeal;
  Object? fetchError;
  int fetches = 0;

  _FakeMealService() : super(_FakeApi());

  @override
  Future<PublicMealDto> getPublicMealByToken(String token) async {
    fetches++;
    if (fetchError != null) throw fetchError!;
    return stubbedMeal!;
  }
}

PublicMealDto _sampleMeal({
  List<PublicMealComponentDto> components = const [],
  String? description = 'Summer lunch',
}) {
  return PublicMealDto(
    id: 'meal-1',
    name: 'Kale Salad Meal',
    description: description,
    recipeBookName: 'Dinners',
    components: components,
  );
}

Widget _harness(
  _FakeMealService svc,
  String token, {
  List<RouteBase>? extraRoutes,
}) {
  final router = GoRouter(
    initialLocation: '/meal-public/$token',
    routes: [
      GoRoute(
        path: '/meal-public/:token',
        builder: (_, state) =>
            PublicMealScreen(token: state.pathParameters['token']!),
      ),
      GoRoute(
        path: '/recipe-public/:token',
        builder: (_, state) => Scaffold(
          body: Center(
            child: Text('recipe-public ${state.pathParameters['token']}'),
          ),
        ),
      ),
      ...?extraRoutes,
    ],
  );
  return MaterialApp.router(routerConfig: router);
}

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  late _FakeMealService service;

  setUp(() {
    service = _FakeMealService();
    final g = GetIt.instance;
    if (g.isRegistered<MealService>()) g.unregister<MealService>();
    g.registerSingleton<MealService>(service);
  });

  tearDown(() {
    final g = GetIt.instance;
    if (g.isRegistered<MealService>()) g.unregister<MealService>();
  });

  testWidgets('renders loading → loaded content with name + components',
      (tester) async {
    service.stubbedMeal = _sampleMeal(components: const [
      PublicMealComponentDto(
        name: 'Lemon Dressing',
        hasPublicToken: true,
        publicToken: 'rtokenA',
      ),
      PublicMealComponentDto(
        name: 'Kale Salad',
        hasPublicToken: false,
      ),
    ]);
    await tester.pumpWidget(_harness(service, 'abc'));
    await tester.pumpAndSettle();

    expect(find.text('Kale Salad Meal'), findsWidgets);
    expect(find.text('Summer lunch'), findsOneWidget);
    expect(find.text('From: Dinners'), findsOneWidget);
    expect(find.text('Recipes (2)'), findsOneWidget);
    expect(find.text('Lemon Dressing'), findsOneWidget);
    expect(find.text('Kale Salad'), findsOneWidget);
    // One public chevron, one lock icon.
    expect(find.byIcon(Icons.chevron_right), findsOneWidget);
    expect(find.byIcon(Icons.lock_outline), findsOneWidget);
    // Footer attribution.
    expect(find.text('Shared via Palateful'), findsOneWidget);
  });

  testWidgets('renders link-off + "isn\'t available" on fetch failure',
      (tester) async {
    service.fetchError = DioException(
      requestOptions: RequestOptions(path: ''),
      response: Response(
        requestOptions: RequestOptions(path: ''),
        statusCode: 404,
      ),
    );
    await tester.pumpWidget(_harness(service, 'bad'));
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.link_off_outlined), findsOneWidget);
    expect(find.text("This meal isn't available."), findsOneWidget);
  });

  testWidgets('tapping a public component navigates to /recipe-public',
      (tester) async {
    service.stubbedMeal = _sampleMeal(components: const [
      PublicMealComponentDto(
        name: 'Lemon Dressing',
        hasPublicToken: true,
        publicToken: 'rtokenA',
      ),
    ]);
    await tester.pumpWidget(_harness(service, 'abc'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Lemon Dressing'));
    await tester.pumpAndSettle();

    expect(find.text('recipe-public rtokenA'), findsOneWidget);
  });

  testWidgets(
    'tapping a private component shows snackbar (no navigation)',
    (tester) async {
      service.stubbedMeal = _sampleMeal(components: const [
        PublicMealComponentDto(
          name: 'Kale Salad',
          hasPublicToken: false,
        ),
      ]);
      await tester.pumpWidget(_harness(service, 'abc'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Kale Salad'));
      await tester.pump();

      expect(
        find.textContaining("This recipe isn't public"),
        findsOneWidget,
      );
      // Still on the meal-public screen, not navigated away.
      expect(find.text('Recipes (1)'), findsOneWidget);
    },
  );

  testWidgets('empty description hides the description block', (tester) async {
    service.stubbedMeal = _sampleMeal(
      description: null,
      components: const [
        PublicMealComponentDto(
          name: 'Lemon Dressing',
          hasPublicToken: true,
          publicToken: 'rtokenA',
        ),
      ],
    );
    await tester.pumpWidget(_harness(service, 'abc'));
    await tester.pumpAndSettle();
    expect(find.text('Summer lunch'), findsNothing);
  });
}
