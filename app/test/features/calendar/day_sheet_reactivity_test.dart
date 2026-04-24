// rmc-3 AC #11 — DayDetailSheet consumes mealEventsByDayProvider and
// re-renders when a matching MealEventCreated event lands on the day.
//
// Pumps the sheet open on a specific date with an initial event, emits
// a second event for the same day, asserts the new title appears.

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/state/mutation_bus.dart';
import 'package:palateful/features/calendar/models/meal_event.dart';
import 'package:palateful/features/calendar/services/meal_calendar_service.dart';
import 'package:palateful/features/calendar/widgets/day_detail_sheet.dart';

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

MealEvent _event(
  String id,
  String title,
  DateTime at,
) =>
    MealEvent(
      id: id,
      title: title,
      scheduledAt: at,
      mealType: MealType.dinner,
      status: 'planned',
      isShared: true,
    );

void main() {
  setUpAll(() async {
  });

  late _FakeMealCalendarService service;
  late DateTime day;
  late DateTime friday;

  setUp(() {
    final gi = GetIt.instance;
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
    gi.registerSingleton<ApiClient>(_FakeApiClient());
    // A fixed Friday in the current year so the sheet's "Fri · ..." label
    // doesn't collide with Today/Tomorrow/Yesterday.
    final now = DateTime.now();
    day = DateTime(now.year, 6, 12); // static-ish day
    // Advance until it's a Friday so the day-of-week label renders as expected.
    friday = day;
    while (friday.weekday != DateTime.friday) {
      friday = friday.add(const Duration(days: 1));
    }
    service = _FakeMealCalendarService(events: [
      _event('evt-a', 'Carbonara', friday.add(const Duration(hours: 19))),
    ]);
    if (gi.isRegistered<MealCalendarService>()) {
      gi.unregister<MealCalendarService>();
    }
    gi.registerSingleton<MealCalendarService>(service);
  });

  tearDown(() {
    final gi = GetIt.instance;
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
    if (gi.isRegistered<MealCalendarService>()) {
      gi.unregister<MealCalendarService>();
    }
  });

  testWidgets(
    'DayDetailSheet re-renders when MealEventCreated lands on the day',
    (tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: DayDetailSheet(
                day: friday,
                calendarId: 'cal-1',
                onMealTap: (_) {},
                onPlanMeal: () {},
              ),
            ),
          ),
        ),
      );
      // First pump is needed for the provider to fire; second pump for the
      // resolved AsyncData frame.
      await tester.pump();
      await tester.pump();

      expect(find.text('Carbonara'), findsOneWidget,
          reason: 'Initial event should render');
      expect(find.text('Garlic Bread'), findsNothing);
      final loadsBefore = service.listCalls;

      // Flip the mocked server state and emit the event.
      service.events = [
        _event('evt-a', 'Carbonara', friday.add(const Duration(hours: 19))),
        _event('evt-b', 'Garlic Bread', friday.add(const Duration(hours: 19, minutes: 30))),
      ];
      emitMutation(MealEventCreated(
        eventId: 'evt-b',
        event: {
          'id': 'evt-b',
          'calendar_id': 'cal-1',
          'scheduled_at': friday
              .add(const Duration(hours: 19, minutes: 30))
              .toUtc()
              .toIso8601String(),
        },
      ));

      // Coalescer: wait past 100ms, then one pump for refetch + one for
      // the rebuilt frame.
      await tester.pump(const Duration(milliseconds: 150));
      await tester.pump();

      expect(service.listCalls, greaterThan(loadsBefore));
      expect(find.text('Carbonara'), findsOneWidget);
      expect(find.text('Garlic Bread'), findsOneWidget,
          reason: 'Newly-created event should appear in the sheet');
    },
  );
}
