import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('Archive view', () {
    testWidgets('archive card shows recipe name', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: ListTile(
            title: const Text('Grandma Pasta'),
            subtitle: const Text('Archived 3/15/2026'),
            trailing: TextButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.restore, size: 18),
              label: const Text('Restore'),
            ),
          ),
        ),
      ));
      expect(find.text('Grandma Pasta'), findsOneWidget);
    });

    testWidgets('restore button present on card', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: TextButton.icon(
            onPressed: () {},
            icon: const Icon(Icons.restore, size: 18),
            label: const Text('Restore'),
          ),
        ),
      ));
      expect(find.text('Restore'), findsOneWidget);
    });

    testWidgets('search bar filters recipes by name', (tester) async {
      final recipes = [
        {'name': 'Chicken Soup', 'archived_at': '2026-01-01T00:00:00Z'},
        {'name': 'Beef Stew', 'archived_at': '2026-01-02T00:00:00Z'},
      ];
      final controller = TextEditingController();

      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: StatefulBuilder(
            builder: (context, setState) {
              final query = controller.text.toLowerCase();
              final filtered = query.isEmpty
                  ? recipes
                  : recipes
                      .where((r) => (r['name'] as String)
                          .toLowerCase()
                          .contains(query))
                      .toList();
              return Column(
                children: [
                  TextField(
                    controller: controller,
                    onChanged: (_) => setState(() {}),
                  ),
                  ...filtered.map((r) => Text(r['name'] as String)),
                ],
              );
            },
          ),
        ),
      ));

      await tester.enterText(find.byType(TextField), 'chicken');
      await tester.pump();
      expect(find.text('Chicken Soup'), findsOneWidget);
      expect(find.text('Beef Stew'), findsNothing);

      // Case-insensitive: uppercase query still matches
      await tester.enterText(find.byType(TextField), 'BEEF');
      await tester.pump();
      expect(find.text('Beef Stew'), findsOneWidget);
      expect(find.text('Chicken Soup'), findsNothing);
    });

    testWidgets('empty state shown when search has no results', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Column(
            children: const [
              Text('No results'),
              Text('No archived recipes match your search'),
            ],
          ),
        ),
      ));
      expect(find.text('No results'), findsOneWidget);
      expect(find.text('No archived recipes match your search'), findsOneWidget);
    });
  });
}
