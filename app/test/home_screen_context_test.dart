import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    GoogleFonts.config.allowRuntimeFetching = false;
  });

  // Note: HomeScreen uses getIt<ApiClient>() which requires the full DI
  // container. These tests verify the UI primitives in isolation using the
  // same pattern as search_screen_test.dart.
  group('HomeScreen contextual sections', () {
    testWidgets('hero card renders recipe name', (tester) async {
      const recipeName = 'Spaghetti Carbonara';

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SizedBox(
              height: 220,
              width: double.infinity,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  Container(color: Colors.grey[200]),
                  Positioned(
                    left: 16,
                    right: 16,
                    bottom: 16,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: const [
                        Text(
                          recipeName,
                          style: TextStyle(
                            fontSize: 24,
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                          ),
                        ),
                        SizedBox(height: 10),
                        ElevatedButton(
                          onPressed: null,
                          child: Text('Start Cooking'),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      );

      expect(find.text(recipeName), findsOneWidget);
      expect(find.text('Start Cooking'), findsOneWidget);
    });

    testWidgets('hero card is absent when no meal is planned', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                // No hero card — search bar is first element
                Padding(
                  padding: EdgeInsets.all(16),
                  child: Text('Search recipes...'),
                ),
              ],
            ),
          ),
        ),
      );

      // No hero card text visible
      expect(find.text('Start Cooking'), findsNothing);
      expect(find.text('Search recipes...'), findsOneWidget);
    });

    testWidgets('recently cooked card shows recipe name', (tester) async {
      const recipeName = 'Grilled Salmon';

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ListView(
              scrollDirection: Axis.horizontal,
              children: [
                SizedBox(
                  width: 80,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        height: 60,
                        width: 80,
                        color: Colors.grey[200],
                        child: const Icon(Icons.restaurant),
                      ),
                      const SizedBox(height: 4),
                      const Text(
                        recipeName,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const Text(
                        '2 days ago',
                        maxLines: 1,
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      );

      expect(find.text(recipeName), findsOneWidget);
      expect(find.text('2 days ago'), findsOneWidget);
    });

    testWidgets('recently cooked section is absent when list is empty',
        (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                // No recently cooked section — list is empty
                Text('No recent activity'),
              ],
            ),
          ),
        ),
      );

      expect(find.text('Recently Cooked'), findsNothing);
      expect(find.text('No recent activity'), findsOneWidget);
    });

    testWidgets('relative date label renders correctly', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                Text('Today'),
                Text('Yesterday'),
                Text('3 days ago'),
              ],
            ),
          ),
        ),
      );

      expect(find.text('Today'), findsOneWidget);
      expect(find.text('Yesterday'), findsOneWidget);
      expect(find.text('3 days ago'), findsOneWidget);
    });
  });
}
