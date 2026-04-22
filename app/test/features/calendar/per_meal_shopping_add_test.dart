import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/features/calendar/calendar_screen.dart';
import 'package:palateful/features/calendar/models/calendar.dart';
import 'package:palateful/features/calendar/models/meal_event.dart';
import 'package:palateful/features/calendar/providers/active_calendar_provider.dart';
import 'package:palateful/features/calendar/services/meal_calendar_service.dart';
import 'package:palateful/features/shopping_cart/models/shopping_list.dart';
import 'package:palateful/features/shopping_cart/services/shopping_cart_service.dart';

Widget _wrap(Widget child) {
  final now = DateTime(2026, 4, 17);
  final cal = Calendar(
    id: 'cal-1',
    name: 'My Calendar',
    ownerId: 'u1',
    userRole: 'owner',
    memberCount: 1,
    createdAt: now,
    updatedAt: now,
    isDefault: true,
  );
  return ProviderScope(
    overrides: [
      calendarsListProvider.overrideWith((ref) async => [cal]),
    ],
    child: MaterialApp(home: child),
  );
}

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

class _FakeAuthService extends AuthService {
  @override
  String? get defaultShoppingListId => null;
}

/// Captures calls to `populateFromRecipe`. Also exposes a gate so tests can
/// simulate a mid-flight reload arriving before the add resolves.
class _FakeShoppingCartService extends ShoppingCartService {
  final List<ShoppingList> _lists;
  final int itemsAddedResult;
  final bool throwOnPopulate;
  String? lastPopulateListId;
  String? lastPopulateRecipeId;
  int populateCallCount = 0;

  /// If non-null, `populateFromRecipe` will await this future before returning.
  Future<void>? gate;

  _FakeShoppingCartService({
    List<ShoppingList> lists = const [],
    this.itemsAddedResult = 3,
    this.throwOnPopulate = false,
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
    populateCallCount++;
    if (gate != null) {
      await gate;
    }
    if (throwOnPopulate) {
      throw Exception('network error');
    }
    return (itemsAdded: itemsAddedResult, itemsSkipped: 0);
  }

  @override
  Future<void> setDefaultShoppingList(String? shoppingListId) async {}
}

class _FakeMealCalendarService implements MealCalendarService {
  List<MealEvent> events;
  _FakeMealCalendarService({this.events = const []});

  @override
  Future<List<MealEvent>> listMealEvents(
    DateTime start,
    DateTime end, {
    String? calendarId,
  }) async =>
      events;

  @override
  Future<MealEvent> getMealEvent(String eventId) async =>
      throw UnimplementedError();

  @override
  Future<MealEvent> createMealEvent({
    required String title,
    required DateTime scheduledAt,
    required MealType mealType,
    required String calendarId,
    String? recipeId,
    String? mealId,
    bool isShared = true,
  }) async =>
      throw UnimplementedError();

  @override
  Future<MealEvent> updateMealEvent(
    String eventId, {
    required DateTime scheduledAt,
    required MealType mealType,
    String? calendarId,
  }) async =>
      throw UnimplementedError();

  @override
  Future<void> deleteMealEvent(String eventId) async {}

  @override
  Future<MealEvent> moveMealEventToCalendar(
          String eventId, String newCalendarId) async =>
      throw UnimplementedError();

  @override
  Future<void> moveRecurrenceRuleToCalendar(
      String ruleId, String newCalendarId) async {}

  @override
  Future<MealEvent> rescheduleMealEvent(
          String eventId, DateTime scheduledAt) async =>
      throw UnimplementedError();

  @override
  Future<void> markMealCompleted(String eventId) async {}

  @override
  Future<RecurrenceRule> createRecurrenceRule({
    required MealType mealType,
    required List<String> weekdays,
    required String interval,
    required DateTime startDate,
    required String tzName,
    required String calendarId,
    String? title,
    String? recipeId,
    String? mealId,
    DateTime? endDate,
    String? monthlyNth,
    bool isShared = true,
  }) async =>
      throw UnimplementedError();

  @override
  Future<List<RecurrenceRule>> listRecurrenceRules() async => [];

  @override
  Future<RecurrenceRule> getRecurrenceRule(String ruleId) async =>
      throw UnimplementedError();

  @override
  Future<void> deleteRecurrenceRule(
    String ruleId, {
    String scope = 'series',
    DateTime? occurrenceDate,
  }) async {}

  @override
  Future<Map<String, dynamic>> updateRecurrenceRule(
    String ruleId, {
    required String scope,
    DateTime? occurrenceDate,
    String? title,
    String? recipeId,
    String? mealType,
    List<String>? weekdays,
    String? interval,
    String? monthlyNth,
    DateTime? endDate,
    bool clearEndDate = false,
    bool? isShared,
    String? tzName,
    String? calendarId,
  }) async =>
      {};
}

ShoppingList _makeList({String id = 'list-1', String name = 'Groceries'}) {
  return ShoppingList(
    id: id,
    name: name,
    ownerId: 'u1',
    createdAt: DateTime.now(),
    updatedAt: DateTime.now(),
  );
}

/// Monday of the current week. Placing fixtures there keeps them in the
/// first (top) day column of the week grid, which is always visible in the
/// 800×600 test viewport — no scrolling required.
DateTime _mondayThisWeek() {
  final now = DateTime.now();
  final d = now.weekday - DateTime.monday;
  return DateTime(now.year, now.month, now.day - d);
}

MealEvent _eventWithRecipe({
  String id = 'evt-1',
  String title = 'Pasta Night',
  DateTime? date,
}) {
  return MealEvent(
    id: id,
    title: title,
    scheduledAt: date ?? _mondayThisWeek(),
    mealType: MealType.dinner,
    status: 'planned',
    isShared: true,
    ownerId: 'u1',
    recipe: const RecipeSummary(id: 'r1', name: 'Pasta Carbonara'),
  );
}

MealEvent _eventWithoutRecipe({
  String id = 'evt-2',
  String title = 'Free Lunch',
  DateTime? date,
}) {
  return MealEvent(
    id: id,
    title: title,
    scheduledAt: date ?? _mondayThisWeek(),
    mealType: MealType.lunch,
    status: 'planned',
    isShared: true,
    ownerId: 'u1',
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

/// The per-card icon is uniquely identified by its `Icons.add_shopping_cart_outlined`
/// glyph (un-added) or `Icons.check` glyph (added). The row-level chevron is
/// `Icons.chevron_right`.
Finder _addCartIconFinder() => find.byIcon(Icons.add_shopping_cart_outlined);

Finder _checkIconFinder() => find.byIcon(Icons.check);

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

  group('AppBar shopping-cart action is gone', () {
    testWidgets('AppBar renders no shopping-cart IconButton or tooltip',
        (tester) async {
      final cartSvc = _FakeShoppingCartService(lists: [_makeList()]);
      _registerAll(
        calSvc: _FakeMealCalendarService(events: [_eventWithoutRecipe()]),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(_wrap(const CalendarScreen()));
      await tester.pumpAndSettle();

      // The AppBar title stays, the week nav stays, but the weekly
      // shopping-cart action is gone. The free-lunch event has no recipe so
      // no per-card icon renders either — so zero add-cart icons total.
      expect(_addCartIconFinder(), findsNothing);
      // The old tooltip is also gone — if someone re-adds an AppBar button
      // with the same tooltip, this catches it.
      expect(find.byTooltip('Add week to shopping list'), findsNothing);
    });
  });

  group('Per-card icon visibility', () {
    testWidgets('renders icon for events with a recipe', (tester) async {
      final cartSvc = _FakeShoppingCartService(lists: [_makeList()]);
      _registerAll(
        calSvc: _FakeMealCalendarService(
          events: [_eventWithRecipe(id: 'evt-1'), _eventWithRecipe(id: 'evt-2', title: 'Salmon')],
        ),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(_wrap(const CalendarScreen()));
      await tester.pumpAndSettle();

      // Two recipe-backed events → two per-card add-cart icons.
      expect(_addCartIconFinder(), findsNWidgets(2));
    });

    testWidgets('hides icon when recipe is null', (tester) async {
      final cartSvc = _FakeShoppingCartService(lists: [_makeList()]);
      _registerAll(
        calSvc: _FakeMealCalendarService(events: [_eventWithoutRecipe()]),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(_wrap(const CalendarScreen()));
      await tester.pumpAndSettle();

      expect(_addCartIconFinder(), findsNothing);
      // No check icon either (nothing has been added).
      expect(_checkIconFinder(), findsNothing);
    });

    testWidgets('icon wrapper is exactly 32x32 logical pixels', (tester) async {
      final cartSvc = _FakeShoppingCartService(lists: [_makeList()]);
      _registerAll(
        calSvc: _FakeMealCalendarService(events: [_eventWithRecipe()]),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(_wrap(const CalendarScreen()));
      await tester.pumpAndSettle();

      // The IconButton is wrapped in a SizedBox(32,32). Locate the parent
      // SizedBox of the IconButton holding the add-cart icon.
      final iconButton = find.ancestor(
        of: _addCartIconFinder(),
        matching: find.byType(IconButton),
      );
      expect(iconButton, findsOneWidget);
      final sized = find.ancestor(
        of: iconButton,
        matching: find.byWidgetPredicate(
          (w) => w is SizedBox && w.width == 32 && w.height == 32,
        ),
      );
      expect(sized, findsOneWidget);
    });
  });

  group('Tap the icon → populateFromRecipe', () {
    testWidgets('calls populateFromRecipe with the event\'s recipe id',
        (tester) async {
      final list = _makeList(id: 'list-42', name: 'Weekly Shop');
      final cartSvc = _FakeShoppingCartService(lists: [list], itemsAddedResult: 5);
      _registerAll(
        calSvc: _FakeMealCalendarService(events: [_eventWithRecipe()]),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(_wrap(const CalendarScreen()));
      await tester.pumpAndSettle();

      await tester.tap(_addCartIconFinder());
      await tester.pumpAndSettle();

      expect(cartSvc.lastPopulateListId, 'list-42');
      expect(cartSvc.lastPopulateRecipeId, 'r1');
      expect(cartSvc.populateCallCount, 1);
    });

    testWidgets('success with items_added > 0 flips icon to check + updates tooltip',
        (tester) async {
      final list = _makeList(name: 'Groceries');
      final cartSvc = _FakeShoppingCartService(lists: [list], itemsAddedResult: 4);
      _registerAll(
        calSvc: _FakeMealCalendarService(events: [_eventWithRecipe()]),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(_wrap(const CalendarScreen()));
      await tester.pumpAndSettle();

      await tester.tap(_addCartIconFinder());
      await tester.pumpAndSettle();

      // Icon flipped.
      expect(_addCartIconFinder(), findsNothing);
      expect(_checkIconFinder(), findsOneWidget);

      // Tooltip flipped (the IconButton's tooltip is injected as a widget
      // we can find by its message string).
      expect(find.byTooltip('Added to shopping list'), findsOneWidget);

      // Snackbar fires.
      expect(find.text('Added 4 ingredients to Groceries'), findsOneWidget);
    });

    testWidgets('items_added == 0 does NOT flip icon; snackbar still fires',
        (tester) async {
      final list = _makeList(name: 'Groceries');
      final cartSvc = _FakeShoppingCartService(lists: [list], itemsAddedResult: 0);
      _registerAll(
        calSvc: _FakeMealCalendarService(events: [_eventWithRecipe()]),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(_wrap(const CalendarScreen()));
      await tester.pumpAndSettle();

      await tester.tap(_addCartIconFinder());
      await tester.pumpAndSettle();

      // Icon stayed as add-cart (no flip).
      expect(_addCartIconFinder(), findsOneWidget);
      expect(_checkIconFinder(), findsNothing);

      // Snackbar still fires with the zero-count wording from the existing handler.
      expect(find.text('Added 0 ingredients to Groceries'), findsOneWidget);
    });

    testWidgets('populateFromRecipe throws → no flip; failure snackbar', (tester) async {
      final list = _makeList(name: 'My List');
      final cartSvc = _FakeShoppingCartService(lists: [list], throwOnPopulate: true);
      _registerAll(
        calSvc: _FakeMealCalendarService(events: [_eventWithRecipe()]),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(_wrap(const CalendarScreen()));
      await tester.pumpAndSettle();

      await tester.tap(_addCartIconFinder());
      await tester.pumpAndSettle();

      expect(_addCartIconFinder(), findsOneWidget);
      expect(_checkIconFinder(), findsNothing);
      expect(find.text('Failed to add ingredients'), findsOneWidget);
    });

    testWidgets('zero shopping lists → snackbar, no flip', (tester) async {
      final cartSvc = _FakeShoppingCartService(lists: []);
      _registerAll(
        calSvc: _FakeMealCalendarService(events: [_eventWithRecipe()]),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(_wrap(const CalendarScreen()));
      await tester.pumpAndSettle();

      await tester.tap(_addCartIconFinder());
      await tester.pumpAndSettle();

      expect(
        find.text('No shopping lists — tap + to create one'),
        findsOneWidget,
      );
      expect(_addCartIconFinder(), findsOneWidget);
      expect(_checkIconFinder(), findsNothing);
      // populateFromRecipe never called.
      expect(cartSvc.populateCallCount, 0);
    });

    testWidgets('icon tap does NOT bubble to the row-level onTap (no meal detail sheet)',
        (tester) async {
      final list = _makeList();
      final cartSvc = _FakeShoppingCartService(lists: [list]);
      _registerAll(
        calSvc: _FakeMealCalendarService(events: [_eventWithRecipe()]),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(_wrap(const CalendarScreen()));
      await tester.pumpAndSettle();

      await tester.tap(_addCartIconFinder());
      await tester.pumpAndSettle();

      // The add flow ran.
      expect(cartSvc.populateCallCount, 1);

      // And the row's `onTap` (which opens `MealDetailSheet`) did NOT also
      // fire. The sheet renders a distinctive "Open Recipe" primary button
      // (see `meal_detail_sheet_test.dart`) — its absence confirms no
      // bubble. If someone regresses the gesture-arena behavior (e.g. by
      // replacing the IconButton with a raw GestureDetector), this fails.
      expect(find.text('Open Recipe'), findsNothing);
    });
  });

  group('Load-generation guard', () {
    testWidgets(
        'mid-flight week-nav during the add does NOT flip the icon',
        (tester) async {
      final list = _makeList();
      final gate = Completer<void>();
      final cartSvc =
          _FakeShoppingCartService(lists: [list], itemsAddedResult: 5);
      cartSvc.gate = gate.future;
      _registerAll(
        calSvc: _FakeMealCalendarService(events: [_eventWithRecipe()]),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(_wrap(const CalendarScreen()));
      await tester.pumpAndSettle();

      // Fire the tap — populateFromRecipe is now awaiting the gate.
      await tester.tap(_addCartIconFinder());
      await tester.pump();

      // User navigates weeks mid-flight. This calls _loadEvents() again which
      // bumps _loadGeneration and clears _addedEventIds. The week-nav
      // chevron is the only `IconButton` with `Icons.chevron_right` — the
      // row-level chevron is a bare `Icon`, not tappable.
      await tester.tap(find.widgetWithIcon(IconButton, Icons.chevron_right));
      await tester.pumpAndSettle();

      // Now release the add future.
      gate.complete();
      await tester.pumpAndSettle();

      // After the gate releases, the success handler runs but the
      // generation has moved on — it MUST NOT write to `_addedEventIds`.
      // The invariant: no `Icons.check` leaks onto any card anywhere on
      // the new grid (whether or not the event re-appears in the week).
      expect(_checkIconFinder(), findsNothing);
    });
  });

  group('Long-press path shares the indicator state', () {
    testWidgets(
        'long-press → Add to shopping list flips the per-card icon on success',
        (tester) async {
      final list = _makeList(name: 'Groceries');
      final cartSvc = _FakeShoppingCartService(lists: [list], itemsAddedResult: 2);
      _registerAll(
        calSvc: _FakeMealCalendarService(events: [_eventWithRecipe()]),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(_wrap(const CalendarScreen()));
      await tester.pumpAndSettle();

      await tester.ensureVisible(find.text('Pasta Night'));
      await tester.longPress(find.text('Pasta Night'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Add to shopping list'));
      await tester.pumpAndSettle();

      // Shared write: the per-card icon in the row flipped.
      expect(_checkIconFinder(), findsOneWidget);
      expect(_addCartIconFinder(), findsNothing);
    });
  });

  group('Semantics label', () {
    testWidgets('un-added reads "Add to shopping list"', (tester) async {
      final cartSvc = _FakeShoppingCartService(lists: [_makeList()]);
      _registerAll(
        calSvc: _FakeMealCalendarService(events: [_eventWithRecipe()]),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(_wrap(const CalendarScreen()));
      await tester.pumpAndSettle();

      final handle = tester.ensureSemantics();
      expect(
        find.bySemanticsLabel('Add to shopping list'),
        findsOneWidget,
      );
      handle.dispose();
    });

    testWidgets(
        'after add, reads "Added to shopping list, double-tap to add again"',
        (tester) async {
      final list = _makeList();
      final cartSvc = _FakeShoppingCartService(lists: [list], itemsAddedResult: 3);
      _registerAll(
        calSvc: _FakeMealCalendarService(events: [_eventWithRecipe()]),
        cartSvc: cartSvc,
      );

      await tester.pumpWidget(_wrap(const CalendarScreen()));
      await tester.pumpAndSettle();

      await tester.tap(_addCartIconFinder());
      await tester.pumpAndSettle();

      final handle = tester.ensureSemantics();
      expect(
        find.bySemanticsLabel('Added to shopping list, double-tap to add again'),
        findsOneWidget,
      );
      handle.dispose();
    });
  });

}
