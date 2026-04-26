import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';

import 'package:palateful/shared/widgets/free_forever_chip.dart';

void main() {
  setUpAll(() {
    GoogleFonts.config.allowRuntimeFetching = false;
  });

  Future<void> pumpChip(WidgetTester tester, Widget chip) async {
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: chip)));
  }

  group('FreeForeverChip', () {
    testWidgets('default flavor renders just the headline', (tester) async {
      await pumpChip(tester, const FreeForeverChip());
      expect(find.text('Unlimited — free forever'), findsOneWidget);
    });

    testWidgets('import flavor renders subtitle', (tester) async {
      await pumpChip(tester, const FreeForeverChip.import());
      expect(find.text('Unlimited — free forever'), findsOneWidget);
      expect(find.text('No 5/week cap. No premium tier.'), findsOneWidget);
    });

    testWidgets('household flavor renders subtitle', (tester) async {
      await pumpChip(tester, const FreeForeverChip.household());
      expect(find.text('Unlimited — free forever'), findsOneWidget);
      expect(find.text('No seat limits. Invite anyone.'), findsOneWidget);
    });

    testWidgets('exposes a single Semantics label combining headline + subtitle',
        (tester) async {
      await pumpChip(tester, const FreeForeverChip.import());
      // Find the wrapper Semantics node from the chip body
      final semantics = tester.getSemantics(find.byType(FreeForeverChip));
      expect(
        semantics.label,
        contains('Unlimited — free forever'),
      );
      expect(
        semantics.label,
        contains('No 5/week cap. No premium tier.'),
      );
    });

    testWidgets('renders without overflow on a 360px-wide canvas',
        (tester) async {
      tester.view.physicalSize = const Size(360, 200);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);

      await pumpChip(
        tester,
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: 16),
          child: Align(
            alignment: Alignment.centerLeft,
            child: FreeForeverChip.import(),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    });
  });
}
