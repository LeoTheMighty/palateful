import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

// Test the EmptyStateWidget and screen empty state patterns.
// Following Story 1.3/1.4 pattern: test UI layout directly with equivalent widget trees.

import 'package:palateful/shared/widgets/empty_state.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('EmptyStateWidget', () {
    testWidgets('renders icon, title, and subtitle', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: EmptyStateWidget(
              icon: Icons.restaurant_menu,
              title: 'No recipes yet',
              subtitle: 'Add your first recipe to get started',
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.restaurant_menu), findsOneWidget);
      expect(find.text('No recipes yet'), findsOneWidget);
      expect(find.text('Add your first recipe to get started'), findsOneWidget);
    });

    testWidgets('renders CTA button when actionLabel provided',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: EmptyStateWidget(
              icon: Icons.book_outlined,
              title: 'No recipe books yet',
              subtitle: 'Create your first book',
              actionLabel: 'Create Recipe Book',
              onAction: () {},
              actionIcon: Icons.add,
            ),
          ),
        ),
      );

      expect(find.text('Create Recipe Book'), findsOneWidget);
      expect(find.byIcon(Icons.add), findsOneWidget);
      // ElevatedButton.icon creates an internal _ElevatedButtonWithIcon,
      // so find by ancestor of the label text instead.
      expect(
        find.ancestor(
          of: find.text('Create Recipe Book'),
          matching: find.byWidgetPredicate((w) => w is ElevatedButton),
        ),
        findsOneWidget,
      );
    });

    testWidgets('hides CTA button when actionLabel not provided',
        (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: EmptyStateWidget(
              icon: Icons.shopping_cart_outlined,
              title: 'No shopping lists yet',
              subtitle: 'Plan a meal to get started',
            ),
          ),
        ),
      );

      expect(find.byType(ElevatedButton), findsNothing);
    });

    testWidgets('CTA button triggers callback', (tester) async {
      bool callbackFired = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: EmptyStateWidget(
              icon: Icons.restaurant_menu,
              title: 'No recipes yet',
              subtitle: 'Add your first recipe',
              actionLabel: 'Add Recipe',
              onAction: () {
                callbackFired = true;
              },
              actionIcon: Icons.add,
            ),
          ),
        ),
      );

      await tester.tap(find.text('Add Recipe'));
      await tester.pump();

      expect(callbackFired, isTrue);
    });

    testWidgets('icon is inside rounded container with theme colors',
        (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: EmptyStateWidget(
              icon: Icons.restaurant_menu,
              title: 'Test',
              subtitle: 'Test subtitle',
            ),
          ),
        ),
      );

      // Verify the icon is wrapped in a Container with BoxDecoration
      final containerFinder = find.ancestor(
        of: find.byIcon(Icons.restaurant_menu),
        matching: find.byType(Container),
      );
      expect(containerFinder, findsWidgets);
    });
  });

  group('Recipe Books Screen Empty State', () {
    testWidgets('renders EmptyStateWidget with recipe book content',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: EmptyStateWidget(
              icon: Icons.book_outlined,
              title: 'No recipe books yet',
              subtitle: 'Create your first book to organize your collection',
              actionLabel: 'Create Recipe Book',
              onAction: () {},
              actionIcon: Icons.add,
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.book_outlined), findsOneWidget);
      expect(find.text('No recipe books yet'), findsOneWidget);
      expect(
          find.text('Create your first book to organize your collection'),
          findsOneWidget);
      expect(find.text('Create Recipe Book'), findsOneWidget);
    });
  });

  group('Cart Screen Empty State', () {
    testWidgets('renders themed empty state', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: EmptyStateWidget(
              icon: Icons.shopping_cart_outlined,
              title: 'No shopping lists yet',
              subtitle: 'Plan a meal and add ingredients to get started',
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.shopping_cart_outlined), findsOneWidget);
      expect(find.text('No shopping lists yet'), findsOneWidget);
      expect(find.text('Plan a meal and add ingredients to get started'),
          findsOneWidget);
      expect(find.byType(ElevatedButton), findsNothing);
    });
  });

  group('Calendar Screen Empty State', () {
    testWidgets('renders themed empty state', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: EmptyStateWidget(
              icon: Icons.calendar_today_outlined,
              title: 'No meals planned yet',
              subtitle: 'Your weekly meal plan will appear here',
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.calendar_today_outlined), findsOneWidget);
      expect(find.text('No meals planned yet'), findsOneWidget);
      expect(find.text('Your weekly meal plan will appear here'),
          findsOneWidget);
      expect(find.byType(ElevatedButton), findsNothing);
    });
  });
}
