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

class _FakeApiClient extends ApiClient {
  @override
  Future<Response> getShoppingLists({int limit = 20, int offset = 0}) async =>
      _fakeResponse({'items': []});
}

/// Captures calls to populateFromCalendarRange.
class _FakeShoppingCartService extends ShoppingCartService {
  final List<ShoppingList> _lists;
  DateTime? lastStart;
  DateTime? lastEnd;
  final int itemsAddedResult;
  final int mealEventsIncludedResult;

  _FakeShoppingCartService({
    List<ShoppingList> lists = const [],
    this.itemsAddedResult = 4,
    this.mealEventsIncludedResult = 2,
  }) : _lists = lists;

  @override
  Future<List<ShoppingList>> getShoppingLists() async => _lists;

  @override
  Future<({int itemsAdded, int itemsSkipped, int mealEventsIncluded})>
      populateFromCalendarRange(
          String listId, DateTime start, DateTime end) async {
    lastStart = start;
    lastEnd = end;
    return (
      itemsAdded: itemsAddedResult,
      itemsSkipped: 0,
      mealEventsIncluded: mealEventsIncludedResult,
    );
  }
}

/// Throws on populateFromCalendarRange — for error path tests.
class _FailingShoppingCartService extends ShoppingCartService {
  final List<ShoppingList> _lists;
  _FailingShoppingCartService({List<ShoppingList> lists = const []})
      : _lists = lists;

  @override
  Future<List<ShoppingList>> getShoppingLists() async => _lists;

  @override
  Future<({int itemsAdded, int itemsSkipped, int mealEventsIncluded})>
      populateFromCalendarRange(
          String listId, DateTime start, DateTime end) async {
    throw Exception('network error');
  }
}

class _FakeAuthService extends AuthService {
  @override
  String? get defaultShoppingListId => null;
}

class _FakeMealCalendarService implements MealCalendarService {
  @override
  Future<List<MealEvent>> listMealEvents(DateTime start, DateTime end) async =>
      [];

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
  required MealCalendarService calSvc,
  required ShoppingCartService cartSvc,
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

  group('Generate weekly shopping list — button visibility', () {
    testWidgets('"Generate" button is visible in CalendarScreen app bar',
        (tester) async {
      final cartSvc = _FakeShoppingCartService(lists: [_makeList()]);
      _registerAll(
        calSvc: _FakeMealCalendarService(),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));
      await tester.pump();

      expect(find.byIcon(Icons.add_shopping_cart_outlined), findsOneWidget);
    });
  });

  group('Generate weekly shopping list — single list', () {
    testWidgets(
        'tapping button calls populateFromCalendarRange with correct dates',
        (tester) async {
      final list = _makeList(id: 'list-42', name: 'Weekly Shop');
      final cartSvc = _FakeShoppingCartService(lists: [list]);
      _registerAll(
        calSvc: _FakeMealCalendarService(),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));
      await tester.pump();

      await tester.tap(find.byIcon(Icons.add_shopping_cart_outlined));
      await tester.pumpAndSettle();

      expect(cartSvc.lastStart, isNotNull);
      expect(cartSvc.lastEnd, isNotNull);
      // start must be a Monday, end is start + 6 days
      expect(cartSvc.lastStart!.weekday, DateTime.monday);
      expect(
        cartSvc.lastEnd!.difference(cartSvc.lastStart!).inDays,
        6,
      );
    });

    testWidgets('success snackbar shows correct plural counts', (tester) async {
      final list = _makeList(name: 'Groceries');
      final cartSvc = _FakeShoppingCartService(
        lists: [list],
        itemsAddedResult: 4,
        mealEventsIncludedResult: 2,
      );
      _registerAll(
        calSvc: _FakeMealCalendarService(),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));
      await tester.pump();

      await tester.tap(find.byIcon(Icons.add_shopping_cart_outlined));
      await tester.pumpAndSettle();

      expect(
        find.text('Added 4 ingredients from 2 meals to Groceries'),
        findsOneWidget,
      );
    });

    testWidgets('uses singular for 1 ingredient from 1 meal', (tester) async {
      final list = _makeList(name: 'My List');
      final cartSvc = _FakeShoppingCartService(
        lists: [list],
        itemsAddedResult: 1,
        mealEventsIncludedResult: 1,
      );
      _registerAll(
        calSvc: _FakeMealCalendarService(),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));
      await tester.pump();

      await tester.tap(find.byIcon(Icons.add_shopping_cart_outlined));
      await tester.pumpAndSettle();

      expect(
        find.text('Added 1 ingredient from 1 meal to My List'),
        findsOneWidget,
      );
    });

    testWidgets(
        'shows "No planned meals" snackbar when mealEventsIncluded is 0',
        (tester) async {
      final list = _makeList(name: 'Groceries');
      final cartSvc = _FakeShoppingCartService(
        lists: [list],
        itemsAddedResult: 0,
        mealEventsIncludedResult: 0,
      );
      _registerAll(
        calSvc: _FakeMealCalendarService(),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));
      await tester.pump();

      await tester.tap(find.byIcon(Icons.add_shopping_cart_outlined));
      await tester.pumpAndSettle();

      expect(
        find.text('No planned meals with recipes this week'),
        findsOneWidget,
      );
    });

    testWidgets('shows error snackbar when populateFromCalendarRange throws',
        (tester) async {
      final list = _makeList(name: 'Groceries');
      final gi = GetIt.instance;
      if (gi.isRegistered<MealCalendarService>()) {
        gi.unregister<MealCalendarService>();
      }
      gi.registerSingleton<MealCalendarService>(_FakeMealCalendarService());
      if (gi.isRegistered<ShoppingCartService>()) {
        gi.unregister<ShoppingCartService>();
      }
      gi.registerSingleton<ShoppingCartService>(
          _FailingShoppingCartService(lists: [list]));

      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));
      await tester.pump();

      await tester.tap(find.byIcon(Icons.add_shopping_cart_outlined));
      await tester.pumpAndSettle();

      expect(find.text('Failed to generate shopping list'), findsOneWidget);
    });
  });

  group('Generate weekly shopping list — no lists', () {
    testWidgets('shows snackbar when user has no shopping lists',
        (tester) async {
      final cartSvc = _FakeShoppingCartService(lists: []);
      _registerAll(
        calSvc: _FakeMealCalendarService(),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));
      await tester.pump();

      await tester.tap(find.byIcon(Icons.add_shopping_cart_outlined));
      await tester.pumpAndSettle();

      expect(
        find.text('No shopping lists — tap + to create one'),
        findsOneWidget,
      );
    });
  });

  group('Generate weekly shopping list — multiple lists', () {
    testWidgets('shows list picker when user has multiple shopping lists',
        (tester) async {
      final list1 = _makeList(id: 'list-1', name: 'Groceries');
      final list2 = _makeList(id: 'list-2', name: 'Pharmacy');
      final cartSvc = _FakeShoppingCartService(
        lists: [list1, list2],
        itemsAddedResult: 2,
        mealEventsIncludedResult: 1,
      );
      _registerAll(
        calSvc: _FakeMealCalendarService(),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));
      await tester.pump();

      await tester.tap(find.byIcon(Icons.add_shopping_cart_outlined));
      await tester.pumpAndSettle();

      expect(find.text('Choose a shopping list'), findsOneWidget);
      expect(find.text('Groceries'), findsOneWidget);
      expect(find.text('Pharmacy'), findsOneWidget);
    });

    testWidgets('selecting list from picker uses correct listId',
        (tester) async {
      final list1 = _makeList(id: 'list-1', name: 'Groceries');
      final list2 = _makeList(id: 'list-2', name: 'Pharmacy');
      final cartSvc = _FakeShoppingCartService(
        lists: [list1, list2],
        itemsAddedResult: 3,
        mealEventsIncludedResult: 2,
      );
      _registerAll(
        calSvc: _FakeMealCalendarService(),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));
      await tester.pump();

      await tester.tap(find.byIcon(Icons.add_shopping_cart_outlined));
      await tester.pumpAndSettle();

      // Select the second list from the picker
      await tester.tap(find.text('Pharmacy'));
      await tester.pumpAndSettle();

      expect(
        find.text('Added 3 ingredients from 2 meals to Pharmacy'),
        findsOneWidget,
      );
    });
  });
}
