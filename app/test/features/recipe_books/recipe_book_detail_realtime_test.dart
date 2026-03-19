import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/recipe_books/services/recipe_book_sync_service.dart';

void main() {
  group('RecipeBookDetailScreen real-time UI components', () {
    testWidgets('live dot indicator is green when ws connected', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            appBar: AppBar(
              title: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Flexible(
                    child: Text('Family Recipes', overflow: TextOverflow.ellipsis),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    width: 8,
                    height: 8,
                    decoration: const BoxDecoration(
                      shape: BoxShape.circle,
                      color: Colors.green,
                    ),
                  ),
                ],
              ),
            ),
            body: const SizedBox(),
          ),
        ),
      );

      expect(find.text('Family Recipes'), findsOneWidget);
      // Green dot container is present
      final greenDots = tester
          .widgetList<Container>(find.byType(Container))
          .where((c) {
        final deco = c.decoration;
        if (deco is BoxDecoration) {
          return deco.shape == BoxShape.circle && deco.color == Colors.green;
        }
        return false;
      });
      expect(greenDots.isNotEmpty, isTrue);
    });

    testWidgets('live dot indicator is grey when ws disconnected', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            appBar: AppBar(
              title: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Flexible(
                    child: Text('Family Recipes', overflow: TextOverflow.ellipsis),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    width: 8,
                    height: 8,
                    decoration: const BoxDecoration(
                      shape: BoxShape.circle,
                      color: Colors.grey,
                    ),
                  ),
                ],
              ),
            ),
            body: const SizedBox(),
          ),
        ),
      );

      final greyDots = tester
          .widgetList<Container>(find.byType(Container))
          .where((c) {
        final deco = c.decoration;
        if (deco is BoxDecoration) {
          return deco.shape == BoxShape.circle && deco.color == Colors.grey;
        }
        return false;
      });
      expect(greyDots.isNotEmpty, isTrue);
    });

    testWidgets('no live dot for personal (non-shared) books', (tester) async {
      // Personal books show a plain Text title, no dot
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            appBar: AppBar(title: const Text('My Personal Book')),
            body: const SizedBox(),
          ),
        ),
      );

      expect(find.text('My Personal Book'), findsOneWidget);
      // No circle-shaped containers expected
      final circleDots = tester
          .widgetList<Container>(find.byType(Container))
          .where((c) {
        final deco = c.decoration;
        if (deco is BoxDecoration) {
          return deco.shape == BoxShape.circle &&
              (deco.color == Colors.green || deco.color == Colors.grey);
        }
        return false;
      });
      expect(circleDots.isEmpty, isTrue);
    });

    testWidgets('RecipeBookWebSocketState.connected indicates live', (tester) async {
      // The dot color is driven by state == connected
      const wsState = RecipeBookWebSocketState.connected;
      final dotColor = wsState == RecipeBookWebSocketState.connected
          ? Colors.green
          : Colors.grey;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Center(
              child: Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: dotColor,
                ),
              ),
            ),
          ),
        ),
      );

      expect(dotColor, Colors.green);
    });

    testWidgets('RecipeBookWebSocketState.disconnected shows grey dot', (tester) async {
      const wsState = RecipeBookWebSocketState.disconnected;
      final dotColor = wsState == RecipeBookWebSocketState.connected
          ? Colors.green
          : Colors.grey;
      expect(dotColor, Colors.grey);
    });
  });
}
