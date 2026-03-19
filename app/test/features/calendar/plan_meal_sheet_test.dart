import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/features/calendar/models/meal_event.dart';
import 'package:palateful/features/calendar/services/meal_calendar_service.dart';
import 'package:palateful/features/calendar/widgets/plan_meal_sheet.dart';

/// Minimal fake service — no real network.
class _FakeMealCalendarService implements MealCalendarService {
  MealEvent? lastCreated;
  MealEvent? lastUpdated;

  @override
  Future<MealEvent> createMealEvent({
    required String title,
    required DateTime scheduledAt,
    required MealType mealType,
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
  Future<List<MealEvent>> listMealEvents(DateTime start, DateTime end) async => [];

  @override
  Future<void> deleteMealEvent(String eventId) async {}
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

  Widget _buildSheet({
    String? eventId,
    DateTime? initialDate,
    MealType? initialMealType,
  }) {
    return MaterialApp(
      home: Scaffold(
        body: PlanMealSheet(
          recipeId: 'r1',
          recipeName: 'Pasta Carbonara',
          eventId: eventId,
          initialDate: initialDate,
          initialMealType: initialMealType,
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

      expect(find.text('Pasta Carbonara'), findsOneWidget);
    });
  });

  group('PlanMealSheet — meal type selection', () {
    testWidgets('Dinner is selected by default', (tester) async {
      await tester.pumpWidget(_buildSheet());

      // Find the Dinner chip — it should have white text (selected)
      final dinnerFinder = find.text('Dinner');
      expect(dinnerFinder, findsOneWidget);
      final textWidget = tester.widget<Text>(dinnerFinder);
      expect(textWidget.style?.color, Colors.white);
    });

    testWidgets('tapping Lunch chip selects it', (tester) async {
      await tester.pumpWidget(_buildSheet());

      await tester.tap(find.text('Lunch'));
      await tester.pump();

      final lunchText = tester.widget<Text>(find.text('Lunch'));
      expect(lunchText.style?.color, Colors.white);
    });

    testWidgets('selecting Lunch deselects Dinner', (tester) async {
      await tester.pumpWidget(_buildSheet());

      await tester.tap(find.text('Lunch'));
      await tester.pump();

      // After Lunch selected, Dinner text should not be white
      final dinnerText = tester.widget<Text>(find.text('Dinner'));
      expect(dinnerText.style?.color, isNot(Colors.white));
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
      await tester.pumpWidget(_buildSheet());

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
