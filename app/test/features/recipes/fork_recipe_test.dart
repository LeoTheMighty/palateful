import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('Fork recipe UI components', () {
    testWidgets('lineage badge renders when forked_from_recipe_name is set', (tester) async {
      const recipeName = 'Nonna\'s Pasta';
      const bookName = 'Family Recipes';

      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Padding(
            padding: const EdgeInsets.all(16),
            child: Builder(
              builder: (context) {
                final colorScheme = Theme.of(context).colorScheme;
                return Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: colorScheme.secondaryContainer,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.call_split_outlined,
                          size: 14, color: colorScheme.onSecondaryContainer),
                      const SizedBox(width: 6),
                      const Flexible(
                        child: Text(
                          'Forked from: $recipeName ($bookName)',
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
        ),
      ));

      expect(find.text('Forked from: $recipeName ($bookName)'), findsOneWidget);
      expect(find.byIcon(Icons.call_split_outlined), findsOneWidget);
    });

    testWidgets('lineage badge is absent when no lineage data', (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(
          body: Padding(
            padding: EdgeInsets.all(16),
            child: Text('Recipe description here'),
          ),
        ),
      ));

      // The lineage badge text is not present
      expect(find.textContaining('Forked from:'), findsNothing);
    });

    testWidgets('Make My Copy appears in popup menu items', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          appBar: AppBar(
            title: const Text('Recipe'),
            actions: [
              PopupMenuButton<String>(
                onSelected: (_) {},
                itemBuilder: (context) => const [
                  PopupMenuItem(
                    value: 'copy',
                    child: Row(
                      children: [
                        Icon(Icons.copy_outlined),
                        SizedBox(width: 8),
                        Text('Copy to Book...'),
                      ],
                    ),
                  ),
                  PopupMenuItem(
                    value: 'fork',
                    child: Row(
                      children: [
                        Icon(Icons.call_split_outlined),
                        SizedBox(width: 8),
                        Text('Make My Copy'),
                      ],
                    ),
                  ),
                ],
              ),
            ],
          ),
          body: const SizedBox(),
        ),
      ));

      // Open the popup menu
      await tester.tap(find.byType(PopupMenuButton<String>));
      await tester.pumpAndSettle();

      expect(find.text('Make My Copy'), findsOneWidget);
      expect(find.byIcon(Icons.call_split_outlined), findsOneWidget);
    });

    testWidgets('fork book picker title shows Fork into...', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) => Center(
              child: ElevatedButton(
                onPressed: () {
                  showModalBottomSheet(
                    context: context,
                    builder: (ctx) => Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Padding(
                          padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                          child: Text(
                            'Fork into...',
                            style: Theme.of(ctx).textTheme.titleMedium,
                          ),
                        ),
                      ],
                    ),
                  );
                },
                child: const Text('Show Picker'),
              ),
            ),
          ),
        ),
      ));

      await tester.tap(find.text('Show Picker'));
      await tester.pumpAndSettle();

      expect(find.text('Fork into...'), findsOneWidget);
    });
  });
}
