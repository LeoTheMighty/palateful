import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/calendar/models/calendar.dart';
import 'package:palateful/features/calendar/providers/active_calendar_provider.dart';
import 'package:palateful/features/calendar/widgets/calendar_picker_sheet.dart';
import 'package:palateful/features/calendar/widgets/calendar_switcher_sheet.dart';

Calendar _cal({
  required String id,
  required String name,
  bool isDefault = false,
  String ownerId = 'owner-1',
  String userRole = 'owner',
}) {
  final now = DateTime(2026, 4, 17);
  return Calendar(
    id: id,
    name: name,
    ownerId: ownerId,
    userRole: userRole,
    memberCount: 1,
    createdAt: now,
    updatedAt: now,
    isDefault: isDefault,
  );
}

class _FakeActive extends ActiveCalendarNotifier {
  final String? initialId;
  _FakeActive(this.initialId);

  @override
  Future<String?> build() async => initialId;

  @override
  Future<void> setActive(String calendarId) async {
    state = AsyncData(calendarId);
  }
}

Widget _host({
  required List<Calendar> calendars,
  String? activeId,
  VoidCallback? onCreateCalendar,
  ValueChanged<Calendar>? onOpenSettings,
}) {
  return ProviderScope(
    overrides: [
      calendarsListProvider.overrideWith((ref) async => calendars),
      activeCalendarProvider
          .overrideWith(() => _FakeActive(activeId ?? calendars.first.id)),
    ],
    child: MaterialApp(
      home: Scaffold(
        body: CalendarSwitcherSheet(
          onCreateCalendar: onCreateCalendar,
          onOpenSettings: onOpenSettings,
        ),
      ),
    ),
  );
}

void main() {
  group('CalendarSwitcherSheet', () {
    testWidgets('renders one calendar with active checkmark', (tester) async {
      final cal = _cal(id: 'a', name: 'My Calendar', isDefault: true);
      await tester.pumpWidget(_host(calendars: [cal], activeId: 'a'));
      await tester.pumpAndSettle();

      expect(find.text('Calendars'), findsOneWidget);
      expect(find.text('My Calendar'), findsOneWidget);
      expect(find.text('New Calendar'), findsOneWidget);
      expect(find.byIcon(Icons.check_circle), findsOneWidget);
    });

    testWidgets('renders three calendars', (tester) async {
      final cals = [
        _cal(id: 'a', name: 'My Calendar', isDefault: true),
        _cal(id: 'b', name: 'Meal Prep'),
        _cal(id: 'c', name: 'Date Nights'),
      ];
      await tester.pumpWidget(_host(calendars: cals, activeId: 'b'));
      await tester.pumpAndSettle();

      expect(find.text('My Calendar'), findsOneWidget);
      expect(find.text('Meal Prep'), findsOneWidget);
      expect(find.text('Date Nights'), findsOneWidget);
    });

    testWidgets('row-body tap triggers select (separate from chevron)',
        (tester) async {
      final cal = _cal(id: 'a', name: 'My Calendar', isDefault: true);
      Calendar? settingsOpened;
      await tester.pumpWidget(_host(
        calendars: [cal],
        activeId: 'a',
        onOpenSettings: (c) => settingsOpened = c,
      ));
      await tester.pumpAndSettle();

      // Row body and settings chevron are distinct hit targets.
      expect(
        find.byKey(const Key('calendar-picker-row-body-a')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('calendar-picker-row-settings-a')),
        findsOneWidget,
      );

      // Tap the settings chevron — body onSelect must NOT fire.
      await tester
          .tap(find.byKey(const Key('calendar-picker-row-settings-a')));
      await tester.pumpAndSettle();
      expect(settingsOpened, isNotNull);
      expect(settingsOpened!.id, 'a');
    });
  });

  group('CalendarPickerSheet', () {
    testWidgets('checkmark shown on the active row only', (tester) async {
      final cals = [
        _cal(id: 'a', name: 'First'),
        _cal(id: 'b', name: 'Second'),
      ];
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: CalendarPickerSheet(
              calendars: cals,
              activeId: 'b',
              onSelect: (_) {},
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Exactly one `check_circle`; exactly one `circle_outlined`.
      expect(find.byIcon(Icons.check_circle), findsOneWidget);
      expect(find.byIcon(Icons.circle_outlined), findsOneWidget);
    });
  });
}
