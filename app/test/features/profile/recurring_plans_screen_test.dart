import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/features/calendar/models/meal_event.dart';
import 'package:palateful/features/calendar/services/meal_calendar_service.dart';
import 'package:palateful/features/profile/recurring_plans/recurring_plans_screen.dart';

class _FakeService implements MealCalendarService {
  List<RecurrenceRule> rules = [];
  String? deletedRuleId;
  bool throwOnList = false;

  @override
  Future<List<RecurrenceRule>> listRecurrenceRules() async {
    if (throwOnList) throw Exception('boom');
    return rules;
  }

  @override
  Future<void> deleteRecurrenceRule(
    String ruleId, {
    String scope = 'series',
    DateTime? occurrenceDate,
  }) async {
    deletedRuleId = ruleId;
  }

  // --- unused stubs ---
  @override
  Future<List<MealEvent>> listMealEvents(DateTime start, DateTime end, {String? calendarId}) async =>
      [];
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
  Future<MealEvent> moveMealEventToCalendar(String eventId, String newCalendarId) async => throw UnimplementedError();

  @override
  Future<void> moveRecurrenceRuleToCalendar(String ruleId, String newCalendarId) async {}
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
  Future<RecurrenceRule> getRecurrenceRule(String ruleId) async =>
      throw UnimplementedError();
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

RecurrenceRule _rule({
  String? title,
  DateTime? endDate,
  String id = 'r-1',
}) =>
    RecurrenceRule(
      id: id,
      ownerId: 'u-1',
      mealType: 'dinner',
      weekdays: ['fri'],
      interval: 'weekly',
      startDate: DateTime(2026, 1, 2),
      tzName: 'America/Los_Angeles',
      isShared: false,
      title: title ?? 'Pizza Friday',
      endDate: endDate,
    );

void main() {
  late _FakeService fake;

  setUp(() {
    fake = _FakeService();
    final getIt = GetIt.instance;
    if (getIt.isRegistered<MealCalendarService>()) {
      getIt.unregister<MealCalendarService>();
    }
    getIt.registerSingleton<MealCalendarService>(fake);
  });

  tearDown(() {
    final getIt = GetIt.instance;
    if (getIt.isRegistered<MealCalendarService>()) {
      getIt.unregister<MealCalendarService>();
    }
  });

  Widget _host() => const MaterialApp(home: RecurringPlansScreen());

  testWidgets('renders empty state when no rules exist', (tester) async {
    await tester.pumpWidget(_host());
    await tester.pumpAndSettle();

    expect(find.text('No recurring meal plans yet.'), findsOneWidget);
    expect(find.text('Open calendar'), findsOneWidget);
  });

  testWidgets('renders active rule row', (tester) async {
    fake.rules = [_rule()];
    await tester.pumpWidget(_host());
    await tester.pumpAndSettle();

    expect(find.text('Pizza Friday'), findsOneWidget);
    expect(find.text('Active'), findsOneWidget);
  });

  testWidgets('renders ended rule muted below active ones', (tester) async {
    fake.rules = [
      _rule(id: 'r-active', title: 'Active one'),
      _rule(
        id: 'r-ended',
        title: 'Ended one',
        endDate: DateTime.now().subtract(const Duration(days: 30)),
      ),
    ];
    await tester.pumpWidget(_host());
    await tester.pumpAndSettle();

    expect(find.text('Active one'), findsOneWidget);
    expect(find.text('Ended one'), findsOneWidget);
    expect(find.text('Ended'), findsOneWidget);
  });

  testWidgets('all-ended shows expandable empty state', (tester) async {
    fake.rules = [
      _rule(
        id: 'r-ended',
        title: 'Ended one',
        endDate: DateTime.now().subtract(const Duration(days: 30)),
      ),
    ];
    await tester.pumpWidget(_host());
    await tester.pumpAndSettle();

    expect(find.text('No active recurring plans.'), findsOneWidget);
    expect(
      find.textContaining('1 ended plan hidden'),
      findsOneWidget,
    );

    await tester.tap(find.textContaining('1 ended plan hidden'));
    await tester.pumpAndSettle();

    expect(find.text('Ended one'), findsOneWidget);
  });

  testWidgets('tap on rule opens edit sheet with Delete series',
      (tester) async {
    fake.rules = [_rule()];
    await tester.pumpWidget(_host());
    await tester.pumpAndSettle();

    await tester.tap(find.text('Pizza Friday'));
    await tester.pumpAndSettle();

    expect(find.text('Delete series'), findsOneWidget);
  });

  testWidgets('Delete series → confirm triggers deleteRecurrenceRule',
      (tester) async {
    fake.rules = [_rule()];
    await tester.pumpWidget(_host());
    await tester.pumpAndSettle();

    await tester.tap(find.text('Pizza Friday'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Delete series'));
    await tester.pumpAndSettle();

    // Confirm dialog
    await tester.tap(find.text('Delete'));
    await tester.pumpAndSettle();

    expect(fake.deletedRuleId, 'r-1');
  });

  testWidgets('list error surfaces retry button', (tester) async {
    fake.throwOnList = true;
    await tester.pumpWidget(_host());
    await tester.pumpAndSettle();

    expect(find.text("Couldn't load your recurring plans."), findsOneWidget);
    expect(find.text('Retry'), findsOneWidget);
  });

  testWidgets('Meal-rule row renders meal name + "N recipes" suffix (mcal-9)',
      (tester) async {
    fake.rules = [
      RecurrenceRule(
        id: 'rm-1',
        ownerId: 'u-1',
        mealType: 'dinner',
        weekdays: const ['mon'],
        interval: 'weekly',
        startDate: DateTime(2026, 4, 13),
        tzName: 'America/Los_Angeles',
        isShared: false,
        mealId: 'meal-kale',
        mealSummary: const MealSummary(
          id: 'meal-kale',
          name: 'Kale Salad Meal',
          componentCount: 2,
        ),
      ),
    ];
    await tester.pumpWidget(_host());
    await tester.pumpAndSettle();

    expect(find.textContaining('Kale Salad Meal'), findsOneWidget);
    expect(find.textContaining('2 recipes'), findsOneWidget);
  });
}
