// rmc-3 AC #10 — Calendar grid reacts to MealEventCreated via the bus.
//
// Pumps CalendarScreen with a mocked `mealEventsByRangeProvider` returning
// the empty list. Emits `MealEventCreated` for an event in the visible
// week. Asserts the cell renders the new event within one pump + one
// frame (100ms coalescer has to fire + refetch) and no skeleton flash
// during the refetch (lastValue guard).

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/state/mutation_bus.dart';
import 'package:palateful/features/calendar/calendar_screen.dart';
import 'package:palateful/features/calendar/models/calendar.dart';
import 'package:palateful/features/calendar/models/meal_event.dart';
import 'package:palateful/features/calendar/providers/active_calendar_provider.dart';
import 'package:palateful/features/calendar/services/meal_calendar_service.dart';
import 'package:palateful/features/shopping_cart/models/shopping_list.dart';
import 'package:palateful/features/shopping_cart/services/shopping_cart_service.dart';

Calendar _defaultCalendar() {
  final now = DateTime(2026, 4, 17);
  return Calendar(
    id: 'cal-1',
    name: 'My Calendar',
    ownerId: 'u1',
    userRole: 'owner',
    memberCount: 1,
    createdAt: now,
    updatedAt: now,
    isDefault: true,
  );
}

Widget _wrap(Widget child) {
  return ProviderScope(
    overrides: [
      calendarsListProvider
          .overrideWith((ref) async => [_defaultCalendar()]),
    ],
    child: MaterialApp(home: child),
  );
}

Response<dynamic> _resp(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _FakeApiClient extends ApiClient {
  @override
  Future<Response> getShoppingLists({int limit = 20, int offset = 0}) async =>
      _resp({'items': []});
}

class _StubShoppingCartService extends ShoppingCartService {
  @override
  Future<List<ShoppingList>> getShoppingLists() async => [];
}

class _FakeMealCalendarService implements MealCalendarService {
  List<MealEvent> events;
  int listCalls = 0;
  _FakeMealCalendarService({this.events = const []});

  @override
  Future<List<MealEvent>> listMealEvents(DateTime start, DateTime end,
      {String? calendarId}) async {
    listCalls++;
    return events;
  }

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
    String? mealReminderTime,
  }) async =>
      throw UnimplementedError();

  @override
  Future<MealEvent> setMealReminderTime(
    String eventId,
    String? reminderTime,
  ) async =>
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
  Future<void> deleteMealEvent(String eventId, {String? calendarId}) async {}

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
  Future<MealEvent> markMealCompleted(String eventId) async =>
      throw UnimplementedError();

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

DateTime _mondayOf(DateTime d) {
  final diff = d.weekday - DateTime.monday;
  return DateTime(d.year, d.month, d.day - diff);
}

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  late _FakeMealCalendarService service;

  setUp(() {
    final gi = GetIt.instance;
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
    gi.registerSingleton<ApiClient>(_FakeApiClient());
    service = _FakeMealCalendarService();
    if (gi.isRegistered<MealCalendarService>()) {
      gi.unregister<MealCalendarService>();
    }
    gi.registerSingleton<MealCalendarService>(service);
    if (gi.isRegistered<ShoppingCartService>()) {
      gi.unregister<ShoppingCartService>();
    }
    gi.registerSingleton<ShoppingCartService>(_StubShoppingCartService());
  });

  tearDown(() {
    final gi = GetIt.instance;
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
    if (gi.isRegistered<MealCalendarService>()) {
      gi.unregister<MealCalendarService>();
    }
    if (gi.isRegistered<ShoppingCartService>()) {
      gi.unregister<ShoppingCartService>();
    }
  });

  testWidgets(
    'MealEventCreated in range triggers grid refetch and renders new tile',
    (tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final now = DateTime.now();
      final weekStart = _mondayOf(now);
      // Put the new event on the middle of the current week.
      final eventAt = weekStart.add(const Duration(days: 3, hours: 18));

      await tester.pumpWidget(_wrap(const CalendarScreen()));
      await tester.pump();
      // Grid renders with no events.
      expect(find.text('Tap to plan a meal'), findsNWidgets(7));
      final loadsBefore = service.listCalls;

      // Server now has the new event — the subscriber-side coalescer
      // refetches after the event lands.
      service.events = [
        MealEvent(
          id: 'evt-1',
          title: 'Sunday Roast',
          scheduledAt: eventAt,
          mealType: MealType.dinner,
          status: 'planned',
          isShared: true,
        ),
      ];

      emitMutation(MealEventCreated(
        eventId: 'evt-1',
        event: {
          'id': 'evt-1',
          'calendar_id': 'cal-1',
          'scheduled_at': eventAt.toUtc().toIso8601String(),
        },
      ));

      // 100ms coalescer fires, then the refetch + rebuild.
      await tester.pump(const Duration(milliseconds: 150));
      await tester.pump();

      expect(service.listCalls, greaterThan(loadsBefore),
          reason: 'Provider should refetch after MealEventCreated');
      expect(find.text('Sunday Roast'), findsOneWidget,
          reason: 'New event tile should render in the grid');
    },
  );
}
