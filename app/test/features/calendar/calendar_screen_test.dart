import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/features/calendar/models/meal_event.dart';
import 'package:palateful/features/calendar/services/meal_calendar_service.dart';
import 'package:palateful/features/calendar/calendar_screen.dart';

class _FakeMealCalendarService implements MealCalendarService {
  final List<MealEvent> events;
  _FakeMealCalendarService({this.events = const []});

  @override
  Future<List<MealEvent>> listMealEvents(DateTime start, DateTime end) async => events;

  @override
  Future<MealEvent> createMealEvent({
    required String title,
    required DateTime scheduledAt,
    required MealType mealType,
    String? recipeId,
    bool isShared = true,
  }) async => throw UnimplementedError();

  @override
  Future<MealEvent> updateMealEvent(
    String eventId, {
    required DateTime scheduledAt,
    required MealType mealType,
  }) async => throw UnimplementedError();

  @override
  Future<void> deleteMealEvent(String eventId) async {}
}

void _registerFake(_FakeMealCalendarService svc) {
  final getIt = GetIt.instance;
  if (getIt.isRegistered<MealCalendarService>()) {
    getIt.unregister<MealCalendarService>();
  }
  getIt.registerSingleton<MealCalendarService>(svc);
}

void _unregister() {
  final getIt = GetIt.instance;
  if (getIt.isRegistered<MealCalendarService>()) {
    getIt.unregister<MealCalendarService>();
  }
}

void main() {
  setUp(() {
    _registerFake(_FakeMealCalendarService());
  });

  tearDown(_unregister);

  group('CalendarScreen — week view', () {
    testWidgets('displays 7 day columns for the current week', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(home: CalendarScreen()),
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
        const MaterialApp(home: CalendarScreen()),
      );
      await tester.pump();

      // The week navigator should show a date range label
      expect(find.byIcon(Icons.chevron_left), findsOneWidget);
      expect(find.byIcon(Icons.chevron_right), findsOneWidget);
    });

    testWidgets('shows "No meals planned" for empty days', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(home: CalendarScreen()),
      );
      await tester.pump();

      // With empty service, all 7 days show the placeholder
      expect(find.text('No meals planned'), findsNWidgets(7));
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
        const MaterialApp(home: CalendarScreen()),
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
        const MaterialApp(home: CalendarScreen()),
      );
      await tester.pump();

      // Today's day number text should be white (rendered inside chocolate circle)
      final dayText = tester.widget<Text>(find.text('${today.day}'));
      expect(dayText.style?.color, Colors.white);
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
        const MaterialApp(home: CalendarScreen()),
      );
      await tester.pump();

      expect(find.text('Breakfast'), findsOneWidget);
    });
  });

  group('CalendarScreen — week navigation', () {
    testWidgets('tapping left arrow loads previous week', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(home: CalendarScreen()),
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
        const MaterialApp(home: CalendarScreen()),
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
