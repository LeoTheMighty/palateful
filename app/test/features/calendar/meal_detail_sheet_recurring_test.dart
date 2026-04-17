import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/features/calendar/models/meal_event.dart';
import 'package:palateful/features/calendar/services/meal_calendar_service.dart';
import 'package:palateful/features/calendar/widgets/meal_detail_sheet.dart';

class _FakeService implements MealCalendarService {
  RecurrenceRule? rule;
  String? deletedRuleId;
  bool throwOnGet = false;

  @override
  Future<RecurrenceRule> getRecurrenceRule(String ruleId) async {
    if (throwOnGet) throw Exception('boom');
    return rule!;
  }

  @override
  Future<void> deleteRecurrenceRule(
    String ruleId, {
    String scope = 'series',
    DateTime? occurrenceDate,
  }) async {
    deletedRuleId = ruleId;
  }

  // --- stubs below ---
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
    String? title,
    String? recipeId,
    DateTime? endDate,
    String? monthlyNth,
    bool isShared = true,
  }) async =>
      throw UnimplementedError();
  @override
  Future<List<RecurrenceRule>> listRecurrenceRules() async => [];
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
  }) async =>
      {};
}

MealEvent _recurringEvent() => MealEvent(
      id: 'm-1',
      title: 'Pizza',
      scheduledAt: DateTime(2026, 4, 17, 18, 0),
      mealType: MealType.dinner,
      status: 'planned',
      isShared: false,
      recurrenceRuleId: 'rule-1',
    );

void main() {
  late _FakeService fake;

  setUp(() {
    fake = _FakeService();
    fake.rule = RecurrenceRule(
      id: 'rule-1',
      ownerId: 'u-1',
      mealType: 'dinner',
      weekdays: ['fri'],
      interval: 'weekly',
      startDate: DateTime(2026, 4, 17),
      tzName: 'America/Los_Angeles',
      isShared: false,
      title: 'Pizza',
    );
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

  testWidgets('renders Recurring badge and End series today row', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: MealDetailSheet(
          event: _recurringEvent(),
          onReschedule: (_) async {},
          onUnschedule: () {},
          onMarkCooked: null,
        ),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Recurring'), findsOneWidget);
    expect(find.text('End series today'), findsOneWidget);
  });

  testWidgets('End series today — confirm triggers delete + callback',
      (tester) async {
    var ended = false;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: MealDetailSheet(
          event: _recurringEvent(),
          onReschedule: (_) async {},
          onUnschedule: () {},
          onMarkCooked: null,
          onSeriesEnded: () => ended = true,
        ),
      ),
    ));
    await tester.pumpAndSettle();

    await tester.tap(find.text('End series today'));
    await tester.pumpAndSettle();

    // Confirm dialog.
    expect(find.text('Stop repeating Pizza?'), findsOneWidget);
    await tester.tap(find.text('Stop'));
    await tester.pumpAndSettle();

    expect(fake.deletedRuleId, 'rule-1');
    expect(ended, isTrue);
  });

  testWidgets('End series today — cancel does nothing', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: MealDetailSheet(
          event: _recurringEvent(),
          onReschedule: (_) async {},
          onUnschedule: () {},
          onMarkCooked: null,
        ),
      ),
    ));
    await tester.pumpAndSettle();

    await tester.tap(find.text('End series today'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    expect(fake.deletedRuleId, isNull);
  });

  testWidgets('rule load failure hides the End series row', (tester) async {
    fake.throwOnGet = true;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: MealDetailSheet(
          event: _recurringEvent(),
          onReschedule: (_) async {},
          onUnschedule: () {},
          onMarkCooked: null,
        ),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('End series today'), findsNothing);
    expect(find.text('Recurring meal'), findsOneWidget);
  });

  testWidgets('non-recurring event hides badge and row', (tester) async {
    final event = MealEvent(
      id: 'm-2',
      title: 'Pasta',
      scheduledAt: DateTime(2026, 4, 17, 18, 0),
      mealType: MealType.dinner,
      status: 'planned',
      isShared: false,
    );
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: MealDetailSheet(
          event: event,
          onReschedule: (_) async {},
          onUnschedule: () {},
          onMarkCooked: null,
        ),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Recurring'), findsNothing);
    expect(find.text('End series today'), findsNothing);
  });
}
