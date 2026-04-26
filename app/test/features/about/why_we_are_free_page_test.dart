import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';

import 'package:palateful/features/about/why_we_are_free_page.dart';

void main() {
  setUpAll(() {
    GoogleFonts.config.allowRuntimeFetching = false;
  });

  group('WhyWeAreFreePage', () {
    Future<void> pumpPage(WidgetTester tester, {Size? size}) async {
      if (size != null) {
        tester.view.physicalSize = size;
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.reset);
      }
      await tester.pumpWidget(
        const MaterialApp(home: WhyWeAreFreePage()),
      );
    }

    testWidgets('renders title and three tabs', (tester) async {
      await pumpPage(tester);
      expect(find.text("Why we're free"), findsOneWidget);
      expect(find.text('vs Recime'), findsOneWidget);
      expect(find.text('vs Recipe Notes'), findsOneWidget);
      expect(find.text('vs Mela'), findsOneWidget);
    });

    testWidgets('renders the founder-funded paragraph', (tester) async {
      await pumpPage(tester);
      expect(
        find.textContaining('founder-funded', findRichText: false),
        findsWidgets,
      );
    });

    testWidgets('default tab shows Recime comparison values',
        (tester) async {
      await pumpPage(tester);
      expect(find.text('Recime'), findsOneWidget);
      expect(find.text('\$39.99–\$59.99/yr'), findsOneWidget);
      expect(find.text('Free forever'), findsWidgets);
    });

    testWidgets('switching tab swaps comparison column', (tester) async {
      await pumpPage(tester);
      await tester.tap(find.text('vs Mela'));
      await tester.pumpAndSettle();
      expect(find.text('\$4.99 one-time (iOS)'), findsOneWidget);
    });

    testWidgets('renders without overflow at 360px width', (tester) async {
      await pumpPage(tester, size: const Size(360, 800));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    });

    testWidgets('all 7 comparison row labels appear', (tester) async {
      await pumpPage(tester);
      for (final label in [
        'Price',
        'Import sources',
        'Household sharing',
        'Pantry tracking',
        'Meal planning',
        'Shopping intelligence',
        'Ads',
      ]) {
        expect(find.text(label), findsOneWidget,
            reason: 'expected row "$label" on default tab');
      }
    });
  });
}
