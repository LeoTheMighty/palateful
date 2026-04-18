import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/features/calendar/models/meal_event.dart';
import 'package:palateful/features/calendar/services/meal_calendar_service.dart';
import 'package:palateful/features/calendar/widgets/plan_meal_sheet.dart';

/// Minimal fake service — no real network.
class _FakeMealCalendarService implements MealCalendarService {
  MealEvent? lastCreated;
  MealEvent? lastUpdated;
  Map<String, dynamic>? lastRuleCreated;
  bool throwOnRuleCreate = false;

  @override
  Future<MealEvent> createMealEvent({
    required String title,
    required DateTime scheduledAt,
    required MealType mealType,
    required String calendarId,
    String? recipeId,
    bool isShared = true,
  }) async {
    lastCreated = MealEvent(
      id: 'new-event',
      title: title,
      scheduledAt: scheduledAt,
      mealType: mealType,
      status: 'planned',
      isShared: isShared,
      ownerId: 'user-1',
    );
    return lastCreated!;
  }

  @override
  Future<MealEvent> updateMealEvent(
    String eventId, {
    required DateTime scheduledAt,
    required MealType mealType,
    String? calendarId,
  }) async {
    lastUpdated = MealEvent(
      id: eventId,
      title: 'Updated',
      scheduledAt: scheduledAt,
      mealType: mealType,
      status: 'planned',
      isShared: true,
      ownerId: 'user-1',
    );
    return lastUpdated!;
  }

  @override
  Future<List<MealEvent>> listMealEvents(DateTime start, DateTime end, {String? calendarId}) async => [];

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
    DateTime? endDate,
    String? monthlyNth,
    bool isShared = true,
  }) async {
    if (throwOnRuleCreate) {
      throw Exception('simulated failure');
    }
    lastRuleCreated = {
      'title': title,
      'recipe_id': recipeId,
      'meal_type': mealType.name,
      'weekdays': weekdays,
      'interval': interval,
      'monthly_nth': monthlyNth,
      'start_date': startDate,
      'end_date': endDate,
      'tz_name': tzName,
      'is_shared': isShared,
    };
    return RecurrenceRule(
      id: 'rule-1',
      ownerId: 'user-1',
      mealType: mealType.name,
      weekdays: weekdays,
      interval: interval,
      startDate: startDate,
      tzName: tzName,
      isShared: isShared,
      title: title,
      recipeId: recipeId,
      monthlyNth: monthlyNth,
      endDate: endDate,
    );
  }

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
  late _FakeMealCalendarService fakeService;

  setUp(() {
    fakeService = _FakeMealCalendarService();
    // Register fake in GetIt (replace if already registered)
    final getIt = GetIt.instance;
    if (getIt.isRegistered<MealCalendarService>()) {
      getIt.unregister<MealCalendarService>();
    }
    getIt.registerSingleton<MealCalendarService>(fakeService);
  });

  tearDown(() {
    final getIt = GetIt.instance;
    if (getIt.isRegistered<MealCalendarService>()) {
      getIt.unregister<MealCalendarService>();
    }
  });

  // ignore: no_leading_underscores_for_local_identifiers
  Widget _buildSheet({
    String? eventId,
    DateTime? initialDate,
    MealType? initialMealType,
  }) {
    return ProviderScope(
      child: MaterialApp(
        home: Scaffold(
          body: PlanMealSheet(
            recipeId: 'r1',
            recipeName: 'Pasta Carbonara',
            eventId: eventId,
            initialDate: initialDate,
            initialMealType: initialMealType,
            initialCalendarId: 'cal-test',
          ),
        ),
      ),
    );
  }

  group('PlanMealSheet — layout', () {
    testWidgets('renders date row and 4 meal type chips', (tester) async {
      await tester.pumpWidget(_buildSheet());

      expect(find.byIcon(Icons.calendar_today_outlined), findsOneWidget);
      expect(find.text('Breakfast'), findsOneWidget);
      expect(find.text('Lunch'), findsOneWidget);
      expect(find.text('Dinner'), findsOneWidget);
      expect(find.text('Snack'), findsOneWidget);
    });

    testWidgets('shows "Plan for..." title in create mode', (tester) async {
      await tester.pumpWidget(_buildSheet());

      expect(find.text('Plan for...'), findsOneWidget);
    });

    testWidgets('shows "Reschedule Meal" title in edit mode', (tester) async {
      await tester.pumpWidget(_buildSheet(eventId: 'evt-1'));

      expect(find.text('Reschedule Meal'), findsOneWidget);
    });

    testWidgets('shows recipe name as subtitle', (tester) async {
      await tester.pumpWidget(_buildSheet());

      expect(find.text('Pasta Carbonara'), findsAtLeastNWidgets(1));
    });
  });

  group('PlanMealSheet — meal type selection', () {
    testWidgets('initial meal type chip is selected', (tester) async {
      await tester.pumpWidget(_buildSheet(initialMealType: MealType.dinner));

      // Find the Dinner chip — it should have onPrimary color (selected)
      final dinnerFinder = find.text('Dinner');
      expect(dinnerFinder, findsOneWidget);
      final textWidget = tester.widget<Text>(dinnerFinder);
      final colorScheme = Theme.of(tester.element(find.byType(PlanMealSheet))).colorScheme;
      expect(textWidget.style?.color, colorScheme.onPrimary);
    });

    testWidgets('tapping Lunch chip selects it', (tester) async {
      await tester.pumpWidget(_buildSheet(initialMealType: MealType.dinner));

      await tester.tap(find.text('Lunch'));
      await tester.pump();

      final lunchText = tester.widget<Text>(find.text('Lunch'));
      final colorScheme = Theme.of(tester.element(find.byType(PlanMealSheet))).colorScheme;
      expect(lunchText.style?.color, colorScheme.onPrimary);
    });

    testWidgets('selecting Lunch deselects Dinner', (tester) async {
      await tester.pumpWidget(_buildSheet(initialMealType: MealType.dinner));

      await tester.tap(find.text('Lunch'));
      await tester.pump();

      // After Lunch selected, Dinner text should not be onPrimary
      final dinnerText = tester.widget<Text>(find.text('Dinner'));
      final colorScheme = Theme.of(tester.element(find.byType(PlanMealSheet))).colorScheme;
      expect(dinnerText.style?.color, isNot(colorScheme.onPrimary));
    });
  });

  group('PlanMealSheet — initial values', () {
    testWidgets('uses initialMealType when provided', (tester) async {
      await tester.pumpWidget(_buildSheet(initialMealType: MealType.breakfast));

      final breakfastText = tester.widget<Text>(find.text('Breakfast'));
      expect(breakfastText.style?.color, Colors.white);
    });
  });

  group('PlanMealSheet — save', () {
    testWidgets('Save button calls createMealEvent in create mode',
        (tester) async {
      await tester.pumpWidget(_buildSheet(initialMealType: MealType.dinner));

      await tester.tap(find.text('Add to Calendar'));
      await tester.pump();

      expect(fakeService.lastCreated, isNotNull);
      expect(fakeService.lastCreated!.mealType, MealType.dinner);
    });

    testWidgets('Save button calls updateMealEvent in edit mode',
        (tester) async {
      await tester.pumpWidget(_buildSheet(eventId: 'evt-42'));

      await tester.tap(find.text('Reschedule'));
      await tester.pump();

      expect(fakeService.lastUpdated, isNotNull);
      expect(fakeService.lastUpdated!.id, 'evt-42');
    });
  });
}
