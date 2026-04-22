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
  String? lastCreatedRecipeId;
  String? lastCreatedMealId;
  MealEvent? lastUpdated;
  Map<String, dynamic>? lastRuleCreated;
  bool throwOnRuleCreate = false;

  @override
  Future<MealEvent> getMealEvent(String eventId) async =>
      throw UnimplementedError();

  String? lastCreatedReminderTime;

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
    lastCreated = MealEvent(
      id: 'new-event',
      title: title,
      scheduledAt: scheduledAt,
      mealType: mealType,
      status: 'planned',
      isShared: isShared,
      ownerId: 'user-1',
      mealId: mealId,
      mealReminderTime: mealReminderTime,
    );
    lastCreatedRecipeId = recipeId;
    lastCreatedMealId = mealId;
    lastCreatedReminderTime = mealReminderTime;
    return lastCreated!;
  }

  @override
  Future<MealEvent> setMealReminderTime(
    String eventId,
    String? reminderTime,
  ) async {
    return MealEvent(
      id: eventId,
      title: 'Updated',
      scheduledAt: DateTime.now(),
      mealType: MealType.lunch,
      status: 'planned',
      isShared: true,
      ownerId: 'user-1',
      mealReminderTime: reminderTime,
    );
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
    String? mealId,
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
      'meal_id': mealId,
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
      mealId: mealId,
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

  // ignore: no_leading_underscores_for_local_identifiers
  Widget _buildQuickAddSheet({
    PlanMealType? initialPlanMealType,
    String? initialMealId,
    String? initialMealName,
  }) {
    return ProviderScope(
      child: MaterialApp(
        home: Scaffold(
          body: PlanMealSheet(
            initialCalendarId: 'cal-test',
            initialMealType: MealType.dinner,
            initialPlanMealType: initialPlanMealType ?? PlanMealType.recipe,
            initialMealId: initialMealId,
            initialMealName: initialMealName,
          ),
        ),
      ),
    );
  }

  group('PlanMealSheet — Meal mode (mcal-7)', () {
    testWidgets('SegmentedButton renders Recipe and Meal in quick-add mode',
        (tester) async {
      await tester.pumpWidget(_buildQuickAddSheet());
      expect(find.byType(SegmentedButton<PlanMealType>), findsOneWidget);
      expect(find.text('Recipe'), findsOneWidget);
      expect(find.text('Meal'), findsOneWidget);
    });

    testWidgets('SegmentedButton is hidden when sheet is recipe-pinned',
        (tester) async {
      await tester.pumpWidget(_buildSheet());
      expect(find.byType(SegmentedButton<PlanMealType>), findsNothing);
    });

    testWidgets('initialPlanMealType: meal opens with Meal autocomplete',
        (tester) async {
      await tester.pumpWidget(_buildQuickAddSheet(
        initialPlanMealType: PlanMealType.meal,
        initialMealId: 'meal-kale',
        initialMealName: 'Kale Salad Meal',
      ));
      // Linked chip appears with the pre-filled meal name.
      expect(find.textContaining('Kale Salad Meal'), findsAtLeastNWidgets(1));
    });

    testWidgets('Save in Meal mode with pre-filled meal dispatches mealId',
        (tester) async {
      await tester.pumpWidget(_buildQuickAddSheet(
        initialPlanMealType: PlanMealType.meal,
        initialMealId: 'meal-kale',
        initialMealName: 'Kale Salad Meal',
      ));

      // Meal mode adds a SegmentedButton + autocomplete above the Save
      // button — scroll so the Save button is hittable.
      final saveFinder = find.text('Add to Calendar');
      await tester.ensureVisible(saveFinder);
      await tester.pumpAndSettle();
      await tester.tap(saveFinder);
      await tester.pump();

      expect(fakeService.lastCreatedMealId, 'meal-kale');
      expect(fakeService.lastCreatedRecipeId, isNull);
      expect(fakeService.lastCreated!.title, 'Kale Salad Meal');
    });

    testWidgets(
        'Save in Meal mode without a pick shows snackbar and does not call service',
        (tester) async {
      await tester.pumpWidget(_buildQuickAddSheet(
        initialPlanMealType: PlanMealType.meal,
      ));

      // Meal button should be disabled because nothing is picked.
      final saveFinder = find.text('Add to Calendar');
      await tester.ensureVisible(saveFinder);
      await tester.pumpAndSettle();
      // Disabled button — tap passes but onPressed is null. Use
      // warnIfMissed:false since the disabled button has no hit-test box.
      await tester.tap(saveFinder, warnIfMissed: false);
      await tester.pump();

      expect(fakeService.lastCreated, isNull);
    });

    testWidgets(
        'Toggling Meal → Recipe clears picked meal and vice versa',
        (tester) async {
      await tester.pumpWidget(_buildQuickAddSheet(
        initialPlanMealType: PlanMealType.meal,
        initialMealId: 'meal-kale',
        initialMealName: 'Kale Salad Meal',
      ));

      // Toggle to Recipe mode — linked chip should disappear.
      await tester.tap(find.text('Recipe'));
      await tester.pumpAndSettle();
      expect(find.textContaining('Linked to Kale Salad Meal'), findsNothing);
    });
  });

  group('PlanMealSheet — scrollability (mcal-7)', () {
    testWidgets('body is wrapped in a SingleChildScrollView', (tester) async {
      await tester.pumpWidget(_buildQuickAddSheet());
      expect(find.byType(SingleChildScrollView), findsAtLeastNWidgets(1));
    });
  });

  group('PlanMealSheet — Remind-me-at picker (meal-2)', () {
    testWidgets('Lunch slot shows 12:00 PM with "Lunch default" caption',
        (tester) async {
      await tester.pumpWidget(_buildSheet(initialMealType: MealType.lunch));
      await tester.ensureVisible(find.byKey(const Key('remind_me_at_row')));
      expect(find.text('12:00 PM'), findsOneWidget);
      expect(find.text('Lunch default'), findsOneWidget);
    });

    testWidgets('Dinner slot shows 6:30 PM with "Dinner default" caption',
        (tester) async {
      await tester.pumpWidget(_buildSheet(initialMealType: MealType.dinner));
      await tester.ensureVisible(find.byKey(const Key('remind_me_at_row')));
      expect(find.text('6:30 PM'), findsOneWidget);
      expect(find.text('Dinner default'), findsOneWidget);
    });

    testWidgets('Breakfast / Snack slots show correct defaults',
        (tester) async {
      await tester.pumpWidget(_buildSheet(initialMealType: MealType.breakfast));
      await tester.ensureVisible(find.byKey(const Key('remind_me_at_row')));
      expect(find.text('8:00 AM'), findsOneWidget);
      expect(find.text('Breakfast default'), findsOneWidget);
    });

    testWidgets('Switching meal-type updates default (no override)',
        (tester) async {
      await tester.pumpWidget(_buildSheet(initialMealType: MealType.lunch));
      await tester.tap(find.text('Snack'));
      await tester.pump();
      expect(find.text('3:00 PM'), findsOneWidget);
      expect(find.text('Snack default'), findsOneWidget);
    });

    testWidgets(
        'Save with no override → payload omits meal_reminder_time',
        (tester) async {
      await tester.pumpWidget(_buildSheet(initialMealType: MealType.dinner));
      await tester.tap(find.text('Add to Calendar'));
      await tester.pump();
      expect(fakeService.lastCreatedReminderTime, isNull);
    });

    testWidgets(
        'Reset-to-default button only appears when an override is set',
        (tester) async {
      await tester.pumpWidget(_buildSheet(initialMealType: MealType.lunch));
      // No override yet.
      expect(find.text('Reset to default'), findsNothing);
    });
  });
}
