import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/features/calendar/calendar_screen.dart';
import 'package:palateful/features/calendar/models/meal_event.dart';
import 'package:palateful/features/calendar/services/meal_calendar_service.dart';
import 'package:palateful/features/shopping_cart/models/shopping_list.dart';
import 'package:palateful/features/shopping_cart/services/shopping_cart_service.dart';

// ---------------------------------------------------------------------------
// Fakes
// ---------------------------------------------------------------------------

Response<dynamic> _fakeResponse(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

/// Minimal ApiClient fake — ShoppingCartService reads this from GetIt at init.
class _FakeApiClient extends ApiClient {
  @override
  Future<Response> getShoppingLists({int limit = 20, int offset = 0}) async =>
      _fakeResponse({'items': []});
}

/// Fake ShoppingCartService — captures calls to populateFromRecipe.
class _FakeShoppingCartService extends ShoppingCartService {
  final List<ShoppingList> _lists;
  String? lastPopulateListId;
  String? lastPopulateRecipeId;
  final int itemsAddedResult;

  _FakeShoppingCartService({
    List<ShoppingList> lists = const [],
    this.itemsAddedResult = 3,
  }) : _lists = lists;

  @override
  Future<List<ShoppingList>> getShoppingLists() async => _lists;

  @override
  Future<({int itemsAdded, int itemsSkipped})> populateFromRecipe(
    String listId,
    String recipeId, {
    double scaleFactor = 1.0,
  }) async {
    lastPopulateListId = listId;
    lastPopulateRecipeId = recipeId;
    return (itemsAdded: itemsAddedResult, itemsSkipped: 0);
  }

  @override
  Future<void> setDefaultShoppingList(String? shoppingListId) async {}
}

/// Fake ShoppingCartService that throws on populateFromRecipe — for error path tests.
class _FailingShoppingCartService extends ShoppingCartService {
  final List<ShoppingList> _lists;
  _FailingShoppingCartService({List<ShoppingList> lists = const []})
      : _lists = lists;

  @override
  Future<List<ShoppingList>> getShoppingLists() async => _lists;

  @override
  Future<({int itemsAdded, int itemsSkipped})> populateFromRecipe(
    String listId,
    String recipeId, {
    double scaleFactor = 1.0,
  }) async {
    throw Exception('network error');
  }

  @override
  Future<void> setDefaultShoppingList(String? shoppingListId) async {}
}

class _FakeAuthService extends AuthService {
  @override
  String? get defaultShoppingListId => null;
}

class _FakeMealCalendarService implements MealCalendarService {
  final List<MealEvent> events;
  _FakeMealCalendarService({this.events = const []});

  @override
  Future<List<MealEvent>> listMealEvents(DateTime start, DateTime end) async =>
      events;

  @override
  Future<MealEvent> createMealEvent({
    required String title,
    required DateTime scheduledAt,
    required MealType mealType,
    String? recipeId,
    bool isShared = true,
  }) async =>
      throw UnimplementedError();

  @override
  Future<MealEvent> updateMealEvent(
    String eventId, {
    required DateTime scheduledAt,
    required MealType mealType,
  }) async =>
      throw UnimplementedError();

  @override
  Future<void> deleteMealEvent(String eventId) async {}

  @override
  Future<MealEvent> rescheduleMealEvent(String eventId, DateTime scheduledAt) async =>
      throw UnimplementedError();

  @override
  Future<void> markMealCompleted(String eventId) async {}
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

ShoppingList _makeList({String id = 'list-1', String name = 'Groceries'}) {
  return ShoppingList(
    id: id,
    name: name,
    ownerId: 'u1',
    createdAt: DateTime.now(),
    updatedAt: DateTime.now(),
  );
}

void _registerAll({
  required _FakeMealCalendarService calSvc,
  required _FakeShoppingCartService cartSvc,
}) {
  final gi = GetIt.instance;
  if (gi.isRegistered<MealCalendarService>()) {
    gi.unregister<MealCalendarService>();
  }
  gi.registerSingleton<MealCalendarService>(calSvc);

  if (gi.isRegistered<ShoppingCartService>()) {
    gi.unregister<ShoppingCartService>();
  }
  gi.registerSingleton<ShoppingCartService>(cartSvc);
}

void _unregisterAll() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  if (gi.isRegistered<AuthService>()) gi.unregister<AuthService>();
  if (gi.isRegistered<MealCalendarService>()) {
    gi.unregister<MealCalendarService>();
  }
  if (gi.isRegistered<ShoppingCartService>()) {
    gi.unregister<ShoppingCartService>();
  }
}

MealEvent _eventWithRecipe({DateTime? date}) {
  return MealEvent(
    id: 'evt-1',
    title: 'Pasta Night',
    scheduledAt: date ?? DateTime.now(),
    mealType: MealType.dinner,
    status: 'planned',
    isShared: true,
    ownerId: 'u1',
    recipe: const RecipeSummary(id: 'r1', name: 'Pasta Carbonara'),
  );
}

MealEvent _eventWithoutRecipe({DateTime? date}) {
  return MealEvent(
    id: 'evt-2',
    title: 'Free Lunch',
    scheduledAt: date ?? DateTime.now(),
    mealType: MealType.lunch,
    status: 'planned',
    isShared: true,
    ownerId: 'u1',
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  setUp(() {
    final gi = GetIt.instance;
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
    gi.registerSingleton<ApiClient>(_FakeApiClient());
    if (gi.isRegistered<AuthService>()) gi.unregister<AuthService>();
    gi.registerSingleton<AuthService>(_FakeAuthService());
  });

  tearDown(_unregisterAll);

  group('Add ingredients from calendar — option visibility', () {
    testWidgets(
        'long-press on event WITH recipe shows "Add to shopping list" option',
        (tester) async {
      final cartSvc = _FakeShoppingCartService(lists: [_makeList()]);
      _registerAll(
        calSvc: _FakeMealCalendarService(events: [_eventWithRecipe()]),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));
      await tester.pump();

      await tester.ensureVisible(find.text('Pasta Night'));
      await tester.longPress(find.text('Pasta Night'));
      await tester.pumpAndSettle();

      expect(find.text('Add to shopping list'), findsOneWidget);
    });

    testWidgets(
        'long-press on event WITHOUT recipe does NOT show "Add to shopping list"',
        (tester) async {
      final cartSvc = _FakeShoppingCartService(lists: [_makeList()]);
      _registerAll(
        calSvc: _FakeMealCalendarService(events: [_eventWithoutRecipe()]),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));
      await tester.pump();

      await tester.ensureVisible(find.text('Free Lunch'));
      await tester.longPress(find.text('Free Lunch'));
      await tester.pumpAndSettle();

      expect(find.text('Add to shopping list'), findsNothing);
    });
  });

  group('Add ingredients from calendar — single list', () {
    testWidgets('calls populateFromRecipe with correct list ID and recipe ID',
        (tester) async {
      final list = _makeList(id: 'list-42', name: 'Weekly Shop');
      final cartSvc =
          _FakeShoppingCartService(lists: [list], itemsAddedResult: 5);
      _registerAll(
        calSvc: _FakeMealCalendarService(events: [_eventWithRecipe()]),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));
      await tester.pump();

      await tester.ensureVisible(find.text('Pasta Night'));
      await tester.longPress(find.text('Pasta Night'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Add to shopping list'));
      await tester.pumpAndSettle();

      expect(cartSvc.lastPopulateListId, 'list-42');
      expect(cartSvc.lastPopulateRecipeId, 'r1');
    });

    testWidgets('shows success snackbar with correct ingredient count',
        (tester) async {
      final list = _makeList(name: 'Weekly Shop');
      final cartSvc =
          _FakeShoppingCartService(lists: [list], itemsAddedResult: 4);
      _registerAll(
        calSvc: _FakeMealCalendarService(events: [_eventWithRecipe()]),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));
      await tester.pump();

      await tester.ensureVisible(find.text('Pasta Night'));
      await tester.longPress(find.text('Pasta Night'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Add to shopping list'));
      await tester.pumpAndSettle();

      expect(find.text('Added 4 ingredients to Weekly Shop'), findsOneWidget);
    });

    testWidgets('uses singular "ingredient" when exactly 1 item added',
        (tester) async {
      final list = _makeList(name: 'My List');
      final cartSvc =
          _FakeShoppingCartService(lists: [list], itemsAddedResult: 1);
      _registerAll(
        calSvc: _FakeMealCalendarService(events: [_eventWithRecipe()]),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));
      await tester.pump();

      await tester.ensureVisible(find.text('Pasta Night'));
      await tester.longPress(find.text('Pasta Night'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Add to shopping list'));
      await tester.pumpAndSettle();

      expect(find.text('Added 1 ingredient to My List'), findsOneWidget);
    });
  });

  group('Add ingredients from calendar — no lists', () {
    testWidgets('shows snackbar when user has no shopping lists', (tester) async {
      final cartSvc = _FakeShoppingCartService(lists: []);
      _registerAll(
        calSvc: _FakeMealCalendarService(events: [_eventWithRecipe()]),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));
      await tester.pump();

      await tester.ensureVisible(find.text('Pasta Night'));
      await tester.longPress(find.text('Pasta Night'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Add to shopping list'));
      await tester.pumpAndSettle();

      expect(
        find.text('No shopping lists — tap + to create one'),
        findsOneWidget,
      );
    });
  });

  group('Add ingredients from calendar — error handling', () {
    testWidgets('shows error snackbar when populateFromRecipe fails',
        (tester) async {
      final list = _makeList(name: 'My List');
      final gi = GetIt.instance;
      if (gi.isRegistered<MealCalendarService>()) gi.unregister<MealCalendarService>();
      gi.registerSingleton<MealCalendarService>(
          _FakeMealCalendarService(events: [_eventWithRecipe()]));
      if (gi.isRegistered<ShoppingCartService>()) gi.unregister<ShoppingCartService>();
      gi.registerSingleton<ShoppingCartService>(
          _FailingShoppingCartService(lists: [list]));

      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));
      await tester.pump();

      await tester.ensureVisible(find.text('Pasta Night'));
      await tester.longPress(find.text('Pasta Night'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Add to shopping list'));
      await tester.pumpAndSettle();

      expect(find.text('Failed to add ingredients'), findsOneWidget);
    });
  });

  group('Add ingredients from calendar — multiple lists', () {
    testWidgets('shows list picker when user has multiple shopping lists',
        (tester) async {
      final list1 = _makeList(id: 'list-1', name: 'Groceries');
      final list2 = _makeList(id: 'list-2', name: 'Pharmacy');
      final cartSvc =
          _FakeShoppingCartService(lists: [list1, list2], itemsAddedResult: 2);
      _registerAll(
        calSvc: _FakeMealCalendarService(events: [_eventWithRecipe()]),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));
      await tester.pump();

      await tester.ensureVisible(find.text('Pasta Night'));
      await tester.longPress(find.text('Pasta Night'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Add to shopping list'));
      await tester.pumpAndSettle();

      expect(find.text('Choose a shopping list'), findsOneWidget);
      expect(find.text('Groceries'), findsOneWidget);
      expect(find.text('Pharmacy'), findsOneWidget);
    });

    testWidgets('selecting list from picker calls populateFromRecipe with correct list',
        (tester) async {
      final list1 = _makeList(id: 'list-1', name: 'Groceries');
      final list2 = _makeList(id: 'list-2', name: 'Pharmacy');
      final cartSvc =
          _FakeShoppingCartService(lists: [list1, list2], itemsAddedResult: 3);
      _registerAll(
        calSvc: _FakeMealCalendarService(events: [_eventWithRecipe()]),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));
      await tester.pump();

      await tester.ensureVisible(find.text('Pasta Night'));
      await tester.longPress(find.text('Pasta Night'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Add to shopping list'));
      await tester.pumpAndSettle();

      // Select second list from the picker
      await tester.tap(find.text('Pharmacy'));
      await tester.pumpAndSettle();

      expect(cartSvc.lastPopulateListId, 'list-2');
      expect(cartSvc.lastPopulateRecipeId, 'r1');
      expect(find.text('Added 3 ingredients to Pharmacy'), findsOneWidget);
    });
  });
}
