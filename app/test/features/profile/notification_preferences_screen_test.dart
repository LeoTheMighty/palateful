import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Widget tests for the per-category notification preferences UI
/// shipped in nfn-4. The screen itself depends on getIt-injected
/// services (ApiClient, PushNotificationService) so we exercise the
/// underlying widget patterns + helper logic in isolation rather than
/// mounting the full screen.
void main() {
  group('Categories block — defaults', () {
    testWidgets('all 6 toggles render with their labels', (tester) async {
      await tester.pumpWidget(_categoriesHarness(
        masterOn: true,
        categories: const {
          'meals': true,
          'timers': true,
          'shopping': true,
          'partner_activity': true,
          'imports': true,
          'friends_invitations': true,
        },
      ));

      expect(find.text('Meal reminders'), findsOneWidget);
      expect(find.text('Timers'), findsOneWidget);
      expect(find.text('Shopping'), findsOneWidget);
      expect(find.text('Partner activity'), findsOneWidget);
      expect(find.text('Imports'), findsOneWidget);
      expect(find.text('Friends & invitations'), findsOneWidget);
    });

    testWidgets('all toggles default to ON when categories missing', (tester) async {
      // Empty categories map → defaults to true everywhere.
      await tester.pumpWidget(_categoriesHarness(
        masterOn: true,
        categories: const {},
      ));

      final switches = tester.widgetList<Switch>(find.byType(Switch)).toList();
      expect(switches.length, 6);
      for (final s in switches) {
        expect(s.value, isTrue);
      }
    });
  });

  group('Categories block — user opt-out', () {
    testWidgets('Imports off renders OFF; others stay ON', (tester) async {
      await tester.pumpWidget(_categoriesHarness(
        masterOn: true,
        categories: const {'imports': false},
      ));

      // Find the Imports row's switch by walking from the row label.
      final importsRow = _findRowByLabel(tester, 'Imports');
      expect(importsRow.value, isFalse);

      final mealsRow = _findRowByLabel(tester, 'Meal reminders');
      expect(mealsRow.value, isTrue);
    });

    testWidgets('toggling Meal reminders fires the right key/value',
        (tester) async {
      String? toggledKey;
      bool? toggledValue;

      await tester.pumpWidget(_categoriesHarness(
        masterOn: true,
        categories: const {},
        onToggle: (k, v) {
          toggledKey = k;
          toggledValue = v;
        },
      ));

      // Locate Meal reminders' Switch via the tile-level Material ancestor.
      // (`Material` appears multiple times in the tree from Scaffold +
      // ListView so we walk a few levels up to find the row's Material.)
      final tile = find.widgetWithText(Material, 'Meal reminders').first;
      final switchFinder = find.descendant(
        of: tile,
        matching: find.byType(Switch),
      );
      await tester.tap(switchFinder.first);
      await tester.pump();

      expect(toggledKey, 'meals');
      expect(toggledValue, isFalse);
    });
  });

  group('Categories block — master OFF disables all', () {
    testWidgets('all 6 switches have onChanged=null when master is OFF',
        (tester) async {
      await tester.pumpWidget(_categoriesHarness(
        masterOn: false,
        categories: const {
          'meals': true,
          'timers': true,
          'shopping': true,
          'partner_activity': true,
          'imports': true,
          'friends_invitations': true,
        },
      ));

      final switches = tester.widgetList<Switch>(find.byType(Switch)).toList();
      expect(switches.length, 6);
      for (final s in switches) {
        expect(s.onChanged, isNull,
            reason: 'category switches must be disabled when master is off');
      }
    });

    testWidgets('saved values are preserved (not reset) when master OFF',
        (tester) async {
      // Imports = false should still show as off visually even though disabled.
      await tester.pumpWidget(_categoriesHarness(
        masterOn: false,
        categories: const {'imports': false, 'meals': true},
      ));

      final importsRow = _findRowByLabel(tester, 'Imports');
      expect(importsRow.value, isFalse);
      expect(importsRow.onChanged, isNull);

      final mealsRow = _findRowByLabel(tester, 'Meal reminders');
      expect(mealsRow.value, isTrue);
      expect(mealsRow.onChanged, isNull);
    });
  });
}

// ---------------------------------------------------------------------
// Test harness — mirrors the real screen's category-row structure
// without DI. Asserts the *contract* the production widget must hold.
// ---------------------------------------------------------------------

const _categoryDefs = <(String, String, IconData)>[
  ('meals', 'Meal reminders', Icons.restaurant_menu_outlined),
  ('timers', 'Timers', Icons.timer_outlined),
  ('shopping', 'Shopping', Icons.shopping_cart_outlined),
  ('partner_activity', 'Partner activity', Icons.people_outline),
  ('imports', 'Imports', Icons.cloud_download_outlined),
  ('friends_invitations', 'Friends & invitations',
      Icons.person_add_alt_outlined),
];

Widget _categoriesHarness({
  required bool masterOn,
  required Map<String, bool> categories,
  void Function(String key, bool value)? onToggle,
}) {
  return MaterialApp(
    home: Scaffold(
      body: ListView(
        children: [
          for (final def in _categoryDefs)
            _buildCategoryRow(
              key: def.$1,
              label: def.$2,
              icon: def.$3,
              value: categories[def.$1] ?? true,
              enabled: masterOn,
              onChanged: masterOn ? (v) => onToggle?.call(def.$1, v) : null,
            ),
        ],
      ),
    ),
  );
}

Widget _buildCategoryRow({
  required String key,
  required String label,
  required IconData icon,
  required bool value,
  required bool enabled,
  required ValueChanged<bool>? onChanged,
}) {
  return Builder(builder: (context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final foreground = enabled
        ? colorScheme.onSurface
        : colorScheme.onSurface.withValues(alpha: 0.38);
    return Material(
      color: colorScheme.surfaceContainerHighest.withValues(
        alpha: enabled ? 0.5 : 0.25,
      ),
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Row(
          children: [
            Icon(icon, color: colorScheme.onSurfaceVariant),
            const SizedBox(width: 12),
            Expanded(
              child: Text(label,
                  style: textTheme.bodyLarge?.copyWith(color: foreground)),
            ),
            Switch(value: value, onChanged: enabled ? onChanged : null),
          ],
        ),
      ),
    );
  });
}

Finder _rowFinderForLabel(String label) {
  return find.ancestor(
    of: find.text(label),
    matching: find.byType(Material),
  );
}

Switch _findRowByLabel(WidgetTester tester, String label) {
  final switchFinder = find.descendant(
    of: _rowFinderForLabel(label),
    matching: find.byType(Switch),
  );
  return tester.widgetList<Switch>(switchFinder).first;
}
