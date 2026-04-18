import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/activity/widgets/import_row.dart';

Widget _wrap(Widget child) =>
    MaterialApp(home: Scaffold(body: child));

void main() {
  testWidgets('renders title, status label, chip, trailing, time',
      (tester) async {
    await tester.pumpWidget(_wrap(
      const ImportRow(
        sourceIcon: Icons.link,
        title: 'Chocolate Chip Cookies',
        statusLabel: 'Needs review',
        stateColor: Colors.orange,
        stateChipLabel: 'Needs Review',
        timeLabel: '2m ago',
        trailing: Icon(Icons.chevron_right),
      ),
    ));

    expect(find.text('Chocolate Chip Cookies'), findsOneWidget);
    expect(find.text('Needs review'), findsOneWidget);
    expect(find.text('Needs Review'), findsOneWidget);
    expect(find.text('2m ago'), findsOneWidget);
    expect(find.byIcon(Icons.chevron_right), findsOneWidget);
    expect(find.byIcon(Icons.link), findsOneWidget);
  });

  testWidgets('tap target reports ≥48dp min height', (tester) async {
    await tester.pumpWidget(_wrap(
      const ImportRow(
        sourceIcon: Icons.link,
        title: 'short',
        stateColor: Colors.blue,
      ),
    ));

    final box = tester.getSize(find.byType(ImportRow));
    expect(box.height, greaterThanOrEqualTo(48.0));
  });

  testWidgets('onTap fires when the row is tapped', (tester) async {
    var tapped = 0;
    await tester.pumpWidget(_wrap(
      ImportRow(
        sourceIcon: Icons.link,
        title: 'tap me',
        stateColor: Colors.blue,
        onTap: () => tapped++,
      ),
    ));

    await tester.tap(find.byType(ImportRow));
    expect(tapped, 1);
  });

  testWidgets('accepts a null trailing slot', (tester) async {
    await tester.pumpWidget(_wrap(
      const ImportRow(
        sourceIcon: Icons.link,
        title: 'no trailing',
        stateColor: Colors.blue,
      ),
    ));

    expect(find.text('no trailing'), findsOneWidget);
    // No chevron because no trailing was passed.
    expect(find.byIcon(Icons.chevron_right), findsNothing);
  });
}
