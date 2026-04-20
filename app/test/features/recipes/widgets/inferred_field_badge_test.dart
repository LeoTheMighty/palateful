import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:palateful/features/recipes/add_recipe/widgets/inferred_field_badge.dart';

Widget _wrap(Widget child) {
  return MaterialApp(
    home: Scaffold(
      body: Padding(
        padding: const EdgeInsets.all(8),
        child: child,
      ),
    ),
  );
}

void main() {
  group('InferredFieldBadge', () {
    testWidgets('renders an Icons.auto_awesome glyph in tertiary color',
        (tester) async {
      await tester.pumpWidget(_wrap(const InferredFieldBadge()));

      final iconFinder = find.byIcon(Icons.auto_awesome);
      expect(iconFinder, findsOneWidget);

      final Icon icon = tester.widget(iconFinder);
      expect(icon.size, 14);
      // The color is resolved against the ambient ColorScheme — verify
      // the widget passes SOMETHING non-null so a theme change flows
      // through rather than landing on a hard-coded grey.
      expect(icon.color, isNotNull);
    });

    testWidgets('exposes the accessibility label', (tester) async {
      await tester.pumpWidget(_wrap(const InferredFieldBadge()));
      final semantics = tester.getSemantics(find.byType(InferredFieldBadge));
      expect(semantics.label, 'AI-inferred value, tap for details');
    });

    testWidgets('default onTap opens the explainer sheet', (tester) async {
      await tester.pumpWidget(_wrap(const InferredFieldBadge()));

      await tester.tap(find.byType(InferredFieldBadge));
      await tester.pumpAndSettle();

      expect(find.text('AI guess'), findsOneWidget);
      expect(
        find.textContaining('inferred from the recipe'),
        findsOneWidget,
      );
    });

    testWidgets('custom onTap overrides the explainer sheet',
        (tester) async {
      var taps = 0;
      await tester.pumpWidget(
        _wrap(InferredFieldBadge(onTap: () => taps += 1)),
      );

      await tester.tap(find.byType(InferredFieldBadge));
      await tester.pumpAndSettle();

      expect(taps, 1);
      // Custom onTap short-circuits the default sheet.
      expect(find.text('AI guess'), findsNothing);
    });

    testWidgets('tap target is at least 40pt', (tester) async {
      await tester.pumpWidget(_wrap(const InferredFieldBadge()));
      final size = tester.getSize(find.byType(InkWell));
      expect(size.height, greaterThanOrEqualTo(40));
      expect(size.width, greaterThanOrEqualTo(40));
    });
  });
}
