// rmc-4 AC #3 — end-to-end stress test for the 100ms coalescer wired into
// `mealEventsByRangeProvider`.
//
// Emits 52 `MealEventCreated` back-to-back (simulating a recurrence rule
// materialization). Asserts the provider refetches exactly ONCE during the
// flood + settled window.

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/state/mutation_bus.dart';
import 'package:palateful/features/calendar/calendar_screen.dart';
import 'package:palateful/features/calendar/models/calendar.dart';
import 'package:palateful/features/calendar/models/meal_event.dart';
import 'package:palateful/features/calendar/providers/active_calendar_provider.dart';
import 'package:palateful/features/calendar/providers/meal_events_provider.dart';
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

class _CountingMealCalendarService implements MealCalendarService {
  List<MealEvent> events;
  int listCalls = 0;
  _CountingMealCalendarService({this.events = const []});

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
  });

  late _CountingMealCalendarService service;

  setUp(() {
    final gi = GetIt.instance;
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
    gi.registerSingleton<ApiClient>(_FakeApiClient());
    service = _CountingMealCalendarService();
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
    '52 MealEventCreated in 50ms triggers exactly one refetch',
    (tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      await tester.pumpWidget(_wrap(const CalendarScreen()));
      await tester.pump();

      expect(service.listCalls, 1,
          reason: 'Initial load fires exactly one list call');
      final loadsBefore = service.listCalls;

      final now = DateTime.now();
      final weekStart = _mondayOf(now);

      // Flood the bus with 52 MealEventCreated events (mimics recurrence
      // materialization of 52 occurrences — 1 year weekly).
      final populated = <MealEvent>[];
      for (var i = 0; i < 52; i++) {
        final at = weekStart.add(Duration(hours: i)); // all within the week
        populated.add(MealEvent(
          id: 'evt-$i',
          title: 'E$i',
          scheduledAt: at,
          mealType: MealType.dinner,
          status: 'planned',
          isShared: true,
        ));
      }
      service.events = populated;

      for (var i = 0; i < 52; i++) {
        emitMutation(MealEventCreated(
          eventId: 'evt-$i',
          event: {
            'id': 'evt-$i',
            'calendar_id': 'cal-1',
            'scheduled_at': weekStart
                .add(Duration(hours: i))
                .toUtc()
                .toIso8601String(),
          },
        ));
      }

      // Pump a single microtask — listeners have fired, coalescer is
      // armed with a single pending Timer.
      await tester.pump(Duration.zero);

      // No refetch yet — the 100ms debounce hasn't fired.
      expect(service.listCalls, loadsBefore,
          reason: 'Pending coalescer must not refetch mid-flood');

      // Close the window.
      await tester.pump(const Duration(milliseconds: 120));
      await tester.pump();

      expect(service.listCalls, loadsBefore + 1,
          reason: '52 events should debounce into exactly one refetch');
    },
  );

  testWidgets(
    'provider disposed mid-flood → pending callback cancelled cleanly',
    (tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final container = ProviderContainer(
        overrides: [
          calendarsListProvider
              .overrideWith((ref) async => [_defaultCalendar()]),
        ],
      );
      addTearDown(container.dispose);

      final now = DateTime.now();
      final weekStart = _mondayOf(now);
      final key = MealEventsRangeKey(
        start: weekStart,
        end: weekStart.add(const Duration(days: 6)),
        calendarId: 'cal-1',
      );

      // Subscribe — this triggers the initial fetch.
      final subscription = container.listen<AsyncValue<List<MealEvent>>>(
        mealEventsByRangeProvider(key),
        (_, _) {},
      );
      await container.read(mealEventsByRangeProvider(key).future);
      expect(service.listCalls, 1);

      // Mid-flood: emit, close the subscription before the window fires.
      for (var i = 0; i < 20; i++) {
        emitMutation(MealEventCreated(
          eventId: 'evt-$i',
          event: {
            'id': 'evt-$i',
            'calendar_id': 'cal-1',
            'scheduled_at': weekStart.toUtc().toIso8601String(),
          },
        ));
      }
      subscription.close();
      await tester.pump(const Duration(milliseconds: 200));
      // No second refetch — the provider and its coalescer are gone.
      expect(service.listCalls, 1);
    },
  );
}
