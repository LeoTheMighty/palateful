// Loading is not empty — the calendar must not render "Tap to plan a
// meal" before its first fetch resolves.
//
// The defect: `_buildBody` fell back to an empty event list whenever
// `asyncEvents.value` was null, so a first load drew a full week of
// "Tap to plan a meal" — byte-identical to a genuinely empty calendar.
// A user could not tell "nothing planned" from "we haven't looked yet",
// and the rational reading of both is that the app is broken.
//
// The service here NEVER completes, so the screen is held in its first
// load for the whole test. That is the only state in which the two
// renderings differ: once data arrives, both show the same thing.

import 'dart:async';

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
  late _NeverCompletingService service;

  setUp(() {
    final gi = GetIt.instance;
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
    gi.registerSingleton<ApiClient>(_FakeApiClient());
    service = _NeverCompletingService();
    if (gi.isRegistered<MealCalendarService>()) {
      gi.unregister<MealCalendarService>();
    }
    gi.registerSingleton<MealCalendarService>(service);
    if (gi.isRegistered<ShoppingCartService>()) {
      gi.unregister<ShoppingCartService>();
    }
    gi.registerSingleton<ShoppingCartService>(_StubShoppingCartService());
  });

  testWidgets(
    'first load shows a spinner, not a week of empty-day prompts',
    (tester) async {
      await tester.pumpWidget(_wrap(const CalendarScreen()));
      await tester.pump();

      expect(
        find.byType(CircularProgressIndicator),
        findsWidgets,
        reason: 'the calendar has not fetched yet — it must say so',
      );
      expect(
        find.text('Tap to plan a meal'),
        findsNothing,
        reason:
            'an unfetched calendar must not claim every day is unplanned; '
            'that reading is indistinguishable from a genuinely empty week',
      );
    },
  );

  testWidgets(
    'a genuinely empty week still shows the plan-a-meal prompt',
    (tester) async {
      final gi = GetIt.instance;
      gi.unregister<MealCalendarService>();
      gi.registerSingleton<MealCalendarService>(_FakeMealCalendarService());

      await tester.pumpWidget(_wrap(const CalendarScreen()));
      await tester.pumpAndSettle();

      expect(
        find.text('Tap to plan a meal'),
        findsWidgets,
        reason:
            'the fix must not suppress the real empty state — only the '
            'one rendered before the answer is known',
      );
    },
  );
}

/// Never resolves, so the screen stays in its first load for the test.
class _NeverCompletingService extends _FakeMealCalendarService {
  @override
  Future<List<MealEvent>> listMealEvents(DateTime start, DateTime end,
          {String? calendarId}) =>
      Completer<List<MealEvent>>().future;
}
