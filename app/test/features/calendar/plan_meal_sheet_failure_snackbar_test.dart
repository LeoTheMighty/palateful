// rmc-3 AC #12 — PlanMealSheet failure path routes through
// showMutationFailureSnackbar with MutationType.planMealEvent.
//
// Pumps the sheet with a mocked service that throws on createMealEvent,
// taps Save, asserts the "Couldn't plan meal" Snackbar appears and the
// sheet stays open.

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/calendar/models/calendar.dart';
import 'package:palateful/features/calendar/models/meal_event.dart';
import 'package:palateful/features/calendar/providers/active_calendar_provider.dart';
import 'package:palateful/features/calendar/services/meal_calendar_service.dart';
import 'package:palateful/features/calendar/widgets/plan_meal_sheet.dart';

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

class _FailingMealCalendarService implements MealCalendarService {
  int createCalls = 0;

  @override
  Future<List<MealEvent>> listMealEvents(DateTime start, DateTime end,
      {String? calendarId}) async =>
      const [];

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
  }) async {
    createCalls++;
    throw DioException(
      requestOptions: RequestOptions(path: '/v1/meal-events'),
      response: Response(
        requestOptions: RequestOptions(path: '/v1/meal-events'),
        statusCode: 500,
      ),
    );
  }

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

Widget _wrap(Widget child) {
  return ProviderScope(
    overrides: [
      calendarsListProvider
          .overrideWith((ref) async => [_defaultCalendar()]),
    ],
    child: MaterialApp(home: Scaffold(body: child)),
  );
}

void main() {
  setUpAll(() async {
  });

  late _FailingMealCalendarService service;

  setUp(() {
    final gi = GetIt.instance;
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
    gi.registerSingleton<ApiClient>(_FakeApiClient());
    service = _FailingMealCalendarService();
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
    'createMealEvent failure → showMutationFailureSnackbar with plan copy',
    (tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      await tester.pumpWidget(
        _wrap(
          const PlanMealSheet(
            recipeId: 'r1',
            recipeName: 'Spaghetti Bolognese',
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Tap Save — should invoke createMealEvent, which throws, routing
      // the failure through showMutationFailureSnackbar.
      await tester.tap(find.text('Add to Calendar'));
      await tester.pump();
      await tester.pump();

      expect(service.createCalls, 1,
          reason: 'Save button should invoke createMealEvent');
      expect(find.text("Couldn't plan meal"), findsOneWidget,
          reason: 'Failure copy for MutationType.planMealEvent should appear');
      // Sheet stays open — "Add to Calendar" button still present.
      expect(find.text('Add to Calendar'), findsOneWidget);
    },
  );
}
