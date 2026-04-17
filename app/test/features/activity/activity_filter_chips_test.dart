import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/activity/widgets/activity_filter_chips.dart';

Widget _host({
  required ActivityFilter selected,
  required Set<ActivityFilter> available,
  required ValueChanged<ActivityFilter> onSelected,
}) {
  return MaterialApp(
    home: Scaffold(
      body: ActivityFilterChips(
        selected: selected,
        availableFilters: available,
        onSelected: onSelected,
      ),
    ),
  );
}

void main() {
  testWidgets('renders nothing when only `all` is available', (tester) async {
    await tester.pumpWidget(_host(
      selected: ActivityFilter.all,
      available: const {},
      onSelected: (_) {},
    ));
    expect(find.text('All'), findsNothing);
  });

  testWidgets('renders All and every available filter chip', (tester) async {
    await tester.pumpWidget(_host(
      selected: ActivityFilter.all,
      available: const {ActivityFilter.imports, ActivityFilter.partner},
      onSelected: (_) {},
    ));
    expect(find.text('All'), findsOneWidget);
    expect(find.text('Imports'), findsOneWidget);
    expect(find.text('Partner'), findsOneWidget);
    expect(find.text('Reminders'), findsNothing);
  });

  testWidgets('tapping a chip fires onSelected with that filter',
      (tester) async {
    ActivityFilter? tapped;
    await tester.pumpWidget(_host(
      selected: ActivityFilter.all,
      available: const {ActivityFilter.partner, ActivityFilter.reminders},
      onSelected: (f) => tapped = f,
    ));
    await tester.tap(find.text('Partner'));
    expect(tapped, ActivityFilter.partner);
  });

  test('ActivityFilterX.fromWire covers valid + invalid inputs', () {
    expect(ActivityFilterX.fromWire('imports'), ActivityFilter.imports);
    expect(ActivityFilterX.fromWire('partner'), ActivityFilter.partner);
    expect(ActivityFilterX.fromWire('reminders'), ActivityFilter.reminders);
    expect(ActivityFilterX.fromWire('all'), ActivityFilter.all);
    expect(ActivityFilterX.fromWire(null), ActivityFilter.all);
    expect(ActivityFilterX.fromWire('nonsense'), ActivityFilter.all);
  });

  test('each enum value has a stable wire value', () {
    expect(ActivityFilter.all.wire, 'all');
    expect(ActivityFilter.imports.wire, 'imports');
    expect(ActivityFilter.partner.wire, 'partner');
    expect(ActivityFilter.reminders.wire, 'reminders');
  });
}
