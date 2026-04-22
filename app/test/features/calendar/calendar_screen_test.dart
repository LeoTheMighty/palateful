import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
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

Widget _wrap(Widget child, {List<Calendar>? calendars}) {
  return ProviderScope(
    overrides: [
      calendarsListProvider.overrideWith(
        (ref) async => calendars ?? [_defaultCalendar()],
      ),
    ],
    child: MaterialApp(home: child),
  );
}

Response<dynamic> _fakeResp(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _FakeApiClient extends ApiClient {
  @override
  Future<Response> getShoppingLists({int limit = 20, int offset = 0}) async =>
      _fakeResp({'items': []});
}

class _StubShoppingCartService extends ShoppingCartService {
  @override
  Future<List<ShoppingList>> getShoppingLists() async => [];
}

class _FakeMealCalendarService implements MealCalendarService {
  final List<MealEvent> events;
  _FakeMealCalendarService({this.events = const []});

  @override
  Future<List<MealEvent>> listMealEvents(DateTime start, DateTime end, {String? calendarId}) async => events;

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
  }) async => throw UnimplementedError();

  @override
  Future<MealEvent> updateMealEvent(
    String eventId, {
    required DateTime scheduledAt,
    required MealType mealType,
    String? calendarId,
  }) async => throw UnimplementedError();

  @override
  Future<void> deleteMealEvent(String eventId) async {}

  @override
  Future<MealEvent> moveMealEventToCalendar(String eventId, String newCalendarId) async => throw UnimplementedError();

  @override
  Future<void> moveRecurrenceRuleToCalendar(String ruleId, String newCalendarId) async {}

  @override
  Future<MealEvent> rescheduleMealEvent(String eventId, DateTime scheduledAt) async =>
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

void _registerFake(_FakeMealCalendarService svc) {
  final gi = GetIt.instance;
  if (gi.isRegistered<MealCalendarService>()) gi.unregister<MealCalendarService>();
  gi.registerSingleton<MealCalendarService>(svc);
  if (gi.isRegistered<ShoppingCartService>()) gi.unregister<ShoppingCartService>();
  gi.registerSingleton<ShoppingCartService>(_StubShoppingCartService());
}

void _unregister() {
  final gi = GetIt.instance;
  if (gi.isRegistered<MealCalendarService>()) gi.unregister<MealCalendarService>();
  if (gi.isRegistered<ShoppingCartService>()) gi.unregister<ShoppingCartService>();
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
}

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  setUp(() {
    final gi = GetIt.instance;
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
    gi.registerSingleton<ApiClient>(_FakeApiClient());
    _registerFake(_FakeMealCalendarService());
  });

  tearDown(_unregister);

  group('CalendarScreen — week view', () {
    testWidgets('displays 7 day columns for the current week', (tester) async {
      await tester.pumpWidget(
        _wrap(const CalendarScreen()),
      );
      await tester.pump(); // Let async load complete

      // 7 day names should appear (Mon–Sun)
      const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
      for (final name in dayNames) {
        expect(find.text(name), findsOneWidget,
            reason: 'Expected day column $name to be present');
      }
    });

    testWidgets('shows week range label in app bar', (tester) async {
      await tester.pumpWidget(
        _wrap(const CalendarScreen()),
      );
      await tester.pump();

      // The week navigator should show a date range label
      expect(find.byIcon(Icons.chevron_left), findsOneWidget);
      expect(find.byIcon(Icons.chevron_right), findsOneWidget);
    });

    testWidgets('shows "No meals planned" for empty days', (tester) async {
      await tester.pumpWidget(
        _wrap(const CalendarScreen()),
      );
      await tester.pump();

      // With empty service, all 7 days show the placeholder
      expect(find.text('Tap to plan a meal'), findsNWidgets(7));
    });

    testWidgets('displays event tile with recipe title', (tester) async {
      final today = DateTime.now();
      final event = MealEvent(
        id: 'e1',
        title: 'Pasta Night',
        scheduledAt: today,
        mealType: MealType.dinner,
        status: 'planned',
        isShared: true,
        ownerId: 'u1',
      );

      _registerFake(_FakeMealCalendarService(events: [event]));

      await tester.pumpWidget(
        _wrap(const CalendarScreen()),
      );
      await tester.pump();

      expect(find.text('Pasta Night'), findsOneWidget);
    });

    testWidgets('today column is visually differentiated', (tester) async {
      final today = DateTime.now();
      final event = MealEvent(
        id: 'e1',
        title: 'Today Meal',
        scheduledAt: today,
        mealType: MealType.lunch,
        status: 'planned',
        isShared: false,
        ownerId: 'u1',
      );

      _registerFake(_FakeMealCalendarService(events: [event]));

      await tester.pumpWidget(
        _wrap(const CalendarScreen()),
      );
      await tester.pump();

      // Today's day number text should use onPrimary (rendered inside primary circle)
      final dayText = tester.widget<Text>(find.text('${today.day}'));
      final colorScheme = Theme.of(tester.element(find.byType(CalendarScreen))).colorScheme;
      expect(dayText.style?.color, colorScheme.onPrimary);
    });

    testWidgets('meal type chip is shown on event tile', (tester) async {
      final today = DateTime.now();
      final event = MealEvent(
        id: 'e1',
        title: 'Brunch Time',
        scheduledAt: today,
        mealType: MealType.breakfast,
        status: 'planned',
        isShared: true,
        ownerId: 'u1',
      );

      _registerFake(_FakeMealCalendarService(events: [event]));

      await tester.pumpWidget(
        _wrap(const CalendarScreen()),
      );
      await tester.pump();

      expect(find.text('Breakfast'), findsOneWidget);
    });

    testWidgets('event tile shows total time when recipe has prep+cook time',
        (tester) async {
      final today = DateTime.now();
      final event = MealEvent(
        id: 'e1',
        title: 'Pasta Night',
        scheduledAt: today,
        mealType: MealType.dinner,
        status: 'planned',
        isShared: true,
        ownerId: 'u1',
        recipe: const RecipeSummary(
          id: 'r1',
          name: 'Pasta Carbonara',
          prepTime: 15,
          cookTime: 20,
        ),
      );

      _registerFake(_FakeMealCalendarService(events: [event]));

      await tester.pumpWidget(
        _wrap(const CalendarScreen()),
      );
      await tester.pump();

      expect(find.text('35 min'), findsOneWidget);
    });

    testWidgets('event tile shows prep-only time when only prepTime is set',
        (tester) async {
      final today = DateTime.now();
      final event = MealEvent(
        id: 'e1',
        title: 'Quick Eggs',
        scheduledAt: today,
        mealType: MealType.breakfast,
        status: 'planned',
        isShared: true,
        ownerId: 'u1',
        recipe: const RecipeSummary(
          id: 'r1',
          name: 'Scrambled Eggs',
          prepTime: 15,
          // cookTime omitted → null
        ),
      );

      _registerFake(_FakeMealCalendarService(events: [event]));

      await tester.pumpWidget(
        _wrap(const CalendarScreen()),
      );
      await tester.pump();

      expect(find.text('15 min'), findsOneWidget);
    });

    testWidgets('event tile hides timing row when recipe has no time info',
        (tester) async {
      final today = DateTime.now();
      final event = MealEvent(
        id: 'e1',
        title: 'Quick Snack',
        scheduledAt: today,
        mealType: MealType.snack,
        status: 'planned',
        isShared: true,
        ownerId: 'u1',
        recipe: const RecipeSummary(id: 'r1', name: 'Quick Snack'),
      );

      _registerFake(_FakeMealCalendarService(events: [event]));

      await tester.pumpWidget(
        _wrap(const CalendarScreen()),
      );
      await tester.pump();

      // No timing text should appear (matches only "N min" timing labels)
      expect(find.textContaining(RegExp(r'^\d+ min$')), findsNothing);
    });
  });

  group('CalendarScreen — week navigation', () {
    testWidgets('tapping left arrow loads previous week', (tester) async {
      await tester.pumpWidget(
        _wrap(const CalendarScreen()),
      );
      await tester.pump();

      await tester.tap(find.byIcon(Icons.chevron_left));
      await tester.pump();

      // Still renders 7 day columns after navigation
      const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
      for (final name in dayNames) {
        expect(find.text(name), findsOneWidget);
      }
    });

    testWidgets('tapping right arrow loads next week', (tester) async {
      await tester.pumpWidget(
        _wrap(const CalendarScreen()),
      );
      await tester.pump();

      await tester.tap(find.byIcon(Icons.chevron_right));
      await tester.pump();

      const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
      for (final name in dayNames) {
        expect(find.text(name), findsOneWidget);
      }
    });
  });
}
