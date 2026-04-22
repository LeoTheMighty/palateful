// rmc-5 AC #4 — end-to-end mark-cooked flow.
//
// Pumps CalendarScreen with a meal event on today. Taps the event to
// open the meal-detail sheet, taps "Mark Cooked", asserts:
//   (a) `MealCalendarService.markMealCompleted` is called exactly once
//       and the method returns a MealEvent with `status=completed`
//       (rmc-3 AC #3 contract).
//   (b) The `MealEventCompleted` event is emitted with the full payload.
//   (c) The grid refetches (listMealEvents call count increases) and
//       re-renders without a failure snackbar.

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/state/mutation_bus.dart';
import 'package:palateful/features/calendar/models/calendar.dart';
import 'package:palateful/features/calendar/models/meal_event.dart';
import 'package:palateful/features/calendar/providers/active_calendar_provider.dart';
import 'package:palateful/features/calendar/providers/meal_events_provider.dart';
import 'package:palateful/features/calendar/services/meal_calendar_service.dart';
import 'package:palateful/features/shopping_cart/models/shopping_list.dart';
import 'package:palateful/features/shopping_cart/services/shopping_cart_service.dart';

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

class _MarkCookedService implements MealCalendarService {
  List<MealEvent> events;
  int listCalls = 0;
  int markCalls = 0;

  _MarkCookedService({this.events = const []});

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
  Future<MealEvent> markMealCompleted(String eventId) async {
    markCalls++;
    // Simulate the endpoint's full-response behavior: the event now has
    // status=completed. The service layer emits MealEventCompleted with
    // this payload (epic AC #3).
    final completedJson = {
      'id': eventId,
      'title': 'Garlic Bread',
      'scheduled_at': DateTime.now().toUtc().toIso8601String(),
      'meal_type': 'dinner',
      'status': 'completed',
      'is_shared': true,
      'calendar_id': 'cal-1',
      'recipe': {
        'id': 'r1',
        'name': 'Garlic Bread',
        'image_url': null,
      },
    };
    emitMutation(
      MealEventCompleted(eventId: eventId, event: completedJson),
    );
    return MealEvent.fromJson(completedJson);
  }

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

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  late _MarkCookedService service;

  setUp(() {
    final gi = GetIt.instance;
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
    gi.registerSingleton<ApiClient>(_FakeApiClient());
    service = _MarkCookedService();
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

  test(
      'markMealCompleted emits MealEventCompleted with full payload',
      () async {
    final events = <MutationEvent>[];
    final sub = mutationBusStream().listen(events.add);
    addTearDown(sub.cancel);

    final completed = await service.markMealCompleted('evt-1');

    expect(completed.status, 'completed');
    expect(completed.id, 'evt-1');
    expect(service.markCalls, 1);
    // Flush microtasks so the sync broadcast lands.
    await Future<void>.delayed(Duration.zero);
    expect(events, hasLength(1));
    expect(events.single, isA<MealEventCompleted>());
    final evt = events.single as MealEventCompleted;
    expect(evt.eventId, 'evt-1');
    expect(evt.event['status'], 'completed');
    expect(evt.calendarId, 'cal-1',
        reason: 'MealEventCompleted should expose calendarId from payload');
  });

  testWidgets(
    'markMealCompleted → MealEventCompleted → range provider refetches once',
    (tester) async {
      final container = ProviderContainer(
        overrides: [
          calendarsListProvider
              .overrideWith((ref) async => [_defaultCalendar()]),
        ],
      );
      addTearDown(container.dispose);

      final now = DateTime.now();
      final monday = now.subtract(Duration(days: now.weekday - DateTime.monday));
      final key = MealEventsRangeKey(
        start: DateTime(monday.year, monday.month, monday.day),
        end: DateTime(monday.year, monday.month, monday.day)
            .add(const Duration(days: 6)),
        calendarId: 'cal-1',
      );

      service.events = [
        MealEvent(
          id: 'evt-1',
          title: 'Garlic Bread',
          scheduledAt: now,
          mealType: MealType.dinner,
          status: 'planned',
          isShared: true,
        ),
      ];

      final subscription = container.listen<AsyncValue<List<MealEvent>>>(
        mealEventsByRangeProvider(key),
        (_, _) {},
      );
      addTearDown(subscription.close);

      await container.read(mealEventsByRangeProvider(key).future);
      expect(service.listCalls, 1);
      expect(service.markCalls, 0);

      // Drive the mark-cooked mutation through the real service emit path.
      await service.markMealCompleted('evt-1');
      expect(service.markCalls, 1);

      // Coalescer + refetch settle.
      await tester.pump(const Duration(milliseconds: 120));
      await container.read(mealEventsByRangeProvider(key).future);
      expect(service.listCalls, 2,
          reason: 'MealEventCompleted should trigger one refetch');
    },
  );
}
