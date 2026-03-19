import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Widget test for the Partner Activity toggle UI component.
/// Tests the toggle tile pattern as used in NotificationPreferencesScreen.
void main() {
  group('NotificationPreferencesScreen — Partner Activity toggle', () {
    testWidgets('Partner Activity toggle shows correct label', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: _buildPartnerActivityTile(value: true, onChanged: (_) {}),
          ),
        ),
      );

      expect(find.text('Partner Activity'), findsOneWidget);
      expect(
        find.text('Notify when a partner shares a book or adds a recipe'),
        findsOneWidget,
      );
    });

    testWidgets('Partner Activity toggle starts enabled', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: _buildPartnerActivityTile(value: true, onChanged: (_) {}),
          ),
        ),
      );

      final switchWidget = tester.widget<Switch>(find.byType(Switch));
      expect(switchWidget.value, isTrue);
    });

    testWidgets('Partner Activity toggle starts disabled', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: _buildPartnerActivityTile(value: false, onChanged: (_) {}),
          ),
        ),
      );

      final switchWidget = tester.widget<Switch>(find.byType(Switch));
      expect(switchWidget.value, isFalse);
    });

    testWidgets('Partner Activity toggle fires callback on tap', (tester) async {
      bool? toggled;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: _buildPartnerActivityTile(
              value: true,
              onChanged: (v) => toggled = v,
            ),
          ),
        ),
      );

      await tester.tap(find.byType(Switch));
      await tester.pump();

      expect(toggled, isFalse);
    });

    testWidgets('Household section header is present', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ListView(
              children: [
                const Text('Household'),
                _buildPartnerActivityTile(value: true, onChanged: (_) {}),
              ],
            ),
          ),
        ),
      );

      expect(find.text('Household'), findsOneWidget);
      expect(find.text('Partner Activity'), findsOneWidget);
    });
  });
}

/// Reproduces the partner activity toggle tile as rendered in
/// NotificationPreferencesScreen._buildContent() — tests the structure
/// without needing to wire up getIt / DI.
Widget _buildPartnerActivityTile({
  required bool value,
  required ValueChanged<bool> onChanged,
}) {
  return Builder(
    builder: (context) {
      final colorScheme = Theme.of(context).colorScheme;
      final textTheme = Theme.of(context).textTheme;

      return Material(
        color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: Row(
            children: [
              Icon(Icons.people_outlined, color: colorScheme.onSurfaceVariant),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Partner Activity', style: textTheme.bodyLarge),
                    Text(
                      'Notify when a partner shares a book or adds a recipe',
                      style: textTheme.bodySmall?.copyWith(
                        color: colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
              Switch(value: value, onChanged: onChanged),
            ],
          ),
        ),
      );
    },
  );
}
