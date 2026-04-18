import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/meals/models/meal.dart';
import 'package:palateful/features/meals/services/meal_service.dart';
import 'package:palateful/features/meals/widgets/create_meal_sheet.dart';

class _FakeApi extends ApiClient {
  @override
  Future<Response<dynamic>> getRecipes(
    String bookId, {
    int limit = 20,
    int offset = 0,
    String? search,
  }) async =>
      Response(
        data: {'recipes': <dynamic>[]},
        requestOptions: RequestOptions(path: ''),
        statusCode: 200,
      );

  @override
  Future<Response<dynamic>> search(
    String query, {
    int limit = 20,
    String? bookId,
    List<String>? tags,
    int? maxPrepTime,
    int? maxCookTime,
    String? scope,
  }) async =>
      Response(
        data: {'my_recipes': <dynamic>[]},
        requestOptions: RequestOptions(path: ''),
        statusCode: 200,
      );
}

class _FakeMealService extends MealService {
  _FakeMealService() : super(_FakeApi());

  Map<String, dynamic>? lastCreatePayload;
  String? lastBookId;

  Meal? stubbedMeal;
  Object? stubbedError;

  @override
  Future<Meal> createMeal({
    required String bookId,
    required String name,
    String? description,
    required List<String> componentRecipeIds,
  }) async {
    lastBookId = bookId;
    lastCreatePayload = {
      'name': name,
      if (description != null) 'description': description,
      'component_recipe_ids': componentRecipeIds,
    };
    final err = stubbedError;
    if (err != null) throw err;
    return stubbedMeal ??
        Meal(
          id: 'meal-created',
          name: name,
          recipeBookId: bookId,
          createdAt: DateTime.parse('2026-04-18T10:00:00Z'),
          updatedAt: DateTime.parse('2026-04-18T10:00:00Z'),
        );
  }
}

Meal _meal(String name) => Meal(
      id: 'm-1',
      name: name,
      recipeBookId: 'book-1',
      createdAt: DateTime.parse('2026-04-18T10:00:00Z'),
      updatedAt: DateTime.parse('2026-04-18T10:00:00Z'),
    );

DraftMealComponent _c(String id, String name) =>
    DraftMealComponent(recipeId: id, name: name);

Future<void> _openSheet(
  WidgetTester tester, {
  List<DraftMealComponent>? initial,
  void Function(Meal meal)? onCreated,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: Builder(
          builder: (ctx) => ElevatedButton(
            onPressed: () => CreateMealSheet.show(
              ctx,
              bookId: 'book-1',
              bookName: 'Dinners',
              initialComponents: initial,
              onCreated: onCreated ?? (_) {},
            ),
            child: const Text('Open'),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('Open'));
  // pump through the sheet's slide-in animation AND the standalone
  // mode's post-frame picker open. pumpAndSettle is safe because the
  // standalone picker self-loads from the fake ApiClient and settles.
  await tester.pumpAndSettle();
}

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  late _FakeMealService fakeService;
  late _FakeApi fakeApi;

  setUp(() {
    fakeService = _FakeMealService();
    fakeApi = _FakeApi();
    final g = GetIt.instance;
    if (g.isRegistered<MealService>()) g.unregister<MealService>();
    g.registerSingleton<MealService>(fakeService);
    if (g.isRegistered<ApiClient>()) g.unregister<ApiClient>();
    g.registerSingleton<ApiClient>(fakeApi);
  });

  tearDown(() {
    final g = GetIt.instance;
    if (g.isRegistered<MealService>()) g.unregister<MealService>();
    if (g.isRegistered<ApiClient>()) g.unregister<ApiClient>();
  });

  testWidgets('renders with two initial components and enables Create',
      (tester) async {
    await _openSheet(
      tester,
      initial: [_c('r1', 'Kale Salad'), _c('r2', 'Lemon Dressing')],
    );

    expect(find.text('New meal'), findsOneWidget);
    // Name pre-filled with "Kale Salad + Lemon Dressing"
    final field =
        tester.widget<TextField>(find.widgetWithText(TextField, 'Name'));
    expect(field.controller?.text, 'Kale Salad + Lemon Dressing');
    // Create button should be enabled.
    final create = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Create'),
    );
    expect(create.onPressed, isNotNull);
  });

  testWidgets(
      'long-press drops a component below 2 and disables Create + helper text',
      (tester) async {
    await _openSheet(
      tester,
      initial: [_c('r1', 'Kale Salad'), _c('r2', 'Lemon Dressing')],
    );

    // Tap the X close button on the second thumbnail (Lemon Dressing).
    // Close-icon ordering: [0]=sheet header, [1]=Kale Salad, [2]=Lemon
    // Dressing.
    final closeButtons = find.byIcon(Icons.close);
    expect(closeButtons, findsNWidgets(3));
    await tester.tap(closeButtons.at(2));
    // Snackbar animations + state rebuild.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('A meal needs at least 2 recipes.'), findsOneWidget);
    final create = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Create'),
    );
    expect(create.onPressed, isNull);
  });

  testWidgets('happy-path submit posts payload and calls onCreated',
      (tester) async {
    Meal? received;
    await _openSheet(
      tester,
      initial: [_c('r1', 'Kale Salad'), _c('r2', 'Lemon Dressing')],
      onCreated: (m) => received = m,
    );

    fakeService.stubbedMeal = _meal('Kale Salad + Lemon Dressing');
    await tester.tap(find.widgetWithText(FilledButton, 'Create'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(fakeService.lastBookId, 'book-1');
    expect(fakeService.lastCreatePayload?['name'],
        'Kale Salad + Lemon Dressing');
    expect(
      fakeService.lastCreatePayload?['component_recipe_ids'],
      ['r1', 'r2'],
    );
    // description omitted when empty.
    expect(fakeService.lastCreatePayload?.containsKey('description'), false);
    expect(received?.id, 'm-1');
  });

  testWidgets('cancel dismisses without submit', (tester) async {
    await _openSheet(
      tester,
      initial: [_c('r1', 'Kale Salad'), _c('r2', 'Lemon Dressing')],
    );

    await tester.tap(find.widgetWithText(TextButton, 'Cancel'));
    await tester.pumpAndSettle();

    expect(find.text('New meal'), findsNothing);
    expect(fakeService.lastCreatePayload, isNull);
  });

  testWidgets('name pre-fill truncates to 60 chars + ellipsis', (tester) async {
    final longA = 'A' * 35; // 35
    final longB = 'B' * 40; // 40
    await _openSheet(
      tester,
      initial: [_c('r1', longA), _c('r2', longB)],
    );

    final field =
        tester.widget<TextField>(find.widgetWithText(TextField, 'Name'));
    final text = field.controller!.text;
    expect(text.length, 60);
    expect(text.endsWith('…'), true);
  });

  testWidgets('422 COMPONENT_UNAVAILABLE renders banner + Remove affordance',
      (tester) async {
    await _openSheet(
      tester,
      initial: [_c('r1', 'Kale Salad'), _c('r2', 'Lemon Dressing')],
    );

    fakeService.stubbedError = MealComponentUnavailableException(['r1']);
    await tester.tap(find.widgetWithText(FilledButton, 'Create'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(
      find.textContaining('Some recipes are no longer available'),
      findsOneWidget,
    );
    // The unavailable overlay label should appear.
    expect(find.text('Unavailable'), findsOneWidget);
    // A Remove affordance renders on the flagged row.
    expect(find.widgetWithText(TextButton, 'Remove'), findsOneWidget);
    // Create is disabled because only 1 of 2 components is available.
    final create = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Create'),
    );
    expect(create.onPressed, isNull);
  });

  testWidgets('description is sent when non-empty', (tester) async {
    await _openSheet(
      tester,
      initial: [_c('r1', 'A'), _c('r2', 'B')],
    );

    await tester.enterText(
      find.widgetWithText(TextField, 'Description (optional)'),
      'pairs well',
    );
    await tester.pump();

    fakeService.stubbedMeal = _meal('X');
    await tester.tap(find.widgetWithText(FilledButton, 'Create'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(fakeService.lastCreatePayload?['description'], 'pairs well');
  });

  testWidgets('standalone mode auto-opens the picker on first frame',
      (tester) async {
    // No initialComponents passed — sheet should auto-show picker.
    await _openSheet(tester);
    // Post-frame callback needs another pump.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('Select recipes'), findsOneWidget);
  });

  testWidgets('non-Meal error shows generic error message', (tester) async {
    await _openSheet(
      tester,
      initial: [_c('r1', 'A'), _c('r2', 'B')],
    );

    fakeService.stubbedError = DioException(
      requestOptions: RequestOptions(path: ''),
      response: Response(
        requestOptions: RequestOptions(path: ''),
        statusCode: 500,
        data: {},
      ),
      type: DioExceptionType.badResponse,
    );

    await tester.tap(find.widgetWithText(FilledButton, 'Create'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(
      find.textContaining('Could not create meal'),
      findsOneWidget,
    );
  });
}
