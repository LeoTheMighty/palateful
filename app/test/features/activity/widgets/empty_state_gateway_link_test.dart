import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/activity/widgets/empty_state_gateway_link.dart';

Widget _wrap(Widget child) =>
    MaterialApp(home: Scaffold(body: Center(child: child)));

void main() {
  testWidgets('count == 0 renders nothing', (tester) async {
    await tester.pumpWidget(_wrap(
      EmptyStateGatewayLink(
        count: 0,
        label: 'See past notifications',
        onTap: () {},
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.textContaining('See past notifications'), findsNothing);
    expect(find.byType(Icon), findsNothing);
  });

  testWidgets('count > 0 renders label + count + chevron-down', (tester) async {
    await tester.pumpWidget(_wrap(
      EmptyStateGatewayLink(
        count: 27,
        label: 'See past notifications',
        onTap: () {},
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('See past notifications (27)'), findsOneWidget);
    expect(find.byIcon(Icons.keyboard_arrow_down), findsOneWidget);
  });

  testWidgets('tap fires the onTap callback', (tester) async {
    var taps = 0;
    await tester.pumpWidget(_wrap(
      EmptyStateGatewayLink(
        count: 3,
        label: 'See past imports',
        onTap: () => taps++,
      ),
    ));
    await tester.pumpAndSettle();

    await tester.tap(find.text('See past imports (3)'));
    await tester.pumpAndSettle();
    expect(taps, 1);
  });

  testWidgets('semantic label carries the count and expand hint',
      (tester) async {
    final handle = tester.ensureSemantics();
    await tester.pumpWidget(_wrap(
      EmptyStateGatewayLink(
        count: 27,
        label: 'See past notifications',
        onTap: () {},
      ),
    ));
    await tester.pumpAndSettle();

    expect(
      find.bySemanticsLabel(
          RegExp('See past notifications, 27 items, tap to expand')),
      findsAtLeastNWidgets(1),
    );
    handle.dispose();
  });

  testWidgets('tap target meets the 48dp minimum', (tester) async {
    await tester.pumpWidget(_wrap(
      EmptyStateGatewayLink(
        count: 1,
        label: 'See past notifications',
        onTap: () {},
      ),
    ));
    await tester.pumpAndSettle();

    final box = tester.getSize(find.byType(InkWell));
    expect(box.height, greaterThanOrEqualTo(48.0));
  });
}
