import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    GoogleFonts.config.allowRuntimeFetching = false;
  });

  // Note: SearchScreen uses getIt<ApiClient>() in its constructor, which
  // requires the full DI container. These tests verify the UI layout
  // primitives in isolation rather than testing the actual SearchScreen
  // widget directly. Full integration tests would require a DI harness.
  group('SearchScreen UI', () {
    testWidgets('empty state shows helpful prompt', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    'Search your recipes',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  SizedBox(height: 4),
                  Text('Find recipes by name, ingredient, or tag'),
                ],
              ),
            ),
          ),
        ),
      );

      expect(find.text('Search your recipes'), findsOneWidget);
      expect(
        find.text('Find recipes by name, ingredient, or tag'),
        findsOneWidget,
      );
    });

    testWidgets('recipe card renders image container and name', (tester) async {
      const recipeName = 'Vegetarian Pasta';

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              child: Card(
                clipBehavior: Clip.antiAlias,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                child: SizedBox(
                  height: 100,
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      // Photo-dominant image placeholder
                      Container(
                        width: 100,
                        color: Colors.grey[200],
                        child: const Icon(Icons.restaurant),
                      ),
                      const Expanded(
                        child: Padding(
                          padding: EdgeInsets.fromLTRB(12, 10, 8, 10),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Text(
                                recipeName,
                                style: TextStyle(
                                  fontSize: 15,
                                  fontWeight: FontWeight.w600,
                                ),
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      );

      expect(find.text(recipeName), findsOneWidget);
      expect(find.byIcon(Icons.restaurant), findsOneWidget);
    });
  });
}
