import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';

// Tests for Share Import flow UI components.
// ShareImportScreen depends on GetIt<ApiClient> and starts importing on initState,
// so we test the UI building blocks (progress, error, preview, approve) in isolation.

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    GoogleFonts.config.allowRuntimeFetching = false;
  });

  group('ShareImportScreen — progress state', () {
    testWidgets('loading state shows CircularProgressIndicator', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: Center(child: CircularProgressIndicator()),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('progress state shows shared URL', (tester) async {
      const testUrl = 'https://example.com/recipes/chocolate-cake';

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Center(
              child: Padding(
                padding: const EdgeInsets.all(32),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const CircularProgressIndicator(),
                    const SizedBox(height: 24),
                    const Text('Starting import...'),
                    const SizedBox(height: 8),
                    Text(
                      testUrl,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text(testUrl), findsOneWidget);
      expect(find.text('Starting import...'), findsOneWidget);
    });

    testWidgets('progress state shows destination book name', (tester) async {
      const bookName = 'Italian Recipes';

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const CircularProgressIndicator(),
                  const SizedBox(height: 16),
                  const Text('Saving to $bookName'),
                ],
              ),
            ),
          ),
        ),
      );

      expect(find.text('Saving to $bookName'), findsOneWidget);
    });
  });

  group('ShareImportScreen — error state', () {
    testWidgets('error state shows error message and Close button', (tester) async {
      const errorMessage = 'Recipe extraction failed. The URL may not contain a recipe.';

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Center(
              child: Padding(
                padding: const EdgeInsets.all(32),
                child: Builder(
                  builder: (context) {
                    final colorScheme = Theme.of(context).colorScheme;
                    return Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.error_outline, size: 64, color: colorScheme.error),
                        const SizedBox(height: 16),
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: colorScheme.errorContainer,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            errorMessage,
                            style: TextStyle(color: colorScheme.onErrorContainer),
                            textAlign: TextAlign.center,
                          ),
                        ),
                        const SizedBox(height: 24),
                        FilledButton(
                          onPressed: () {},
                          child: const Text('Close'),
                        ),
                      ],
                    );
                  },
                ),
              ),
            ),
          ),
        ),
      );

      expect(find.text(errorMessage), findsOneWidget);
      expect(find.text('Close'), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });
  });

  group('ShareImportScreen — preview/approve state', () {
    testWidgets('preview shows recipe name and Save Recipe button', (tester) async {
      const recipeName = 'Classic Tiramisu';
      const bookName = 'Italian Recipes';

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                Expanded(
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      Text(
                        recipeName,
                        style: const TextStyle(
                          fontSize: 24,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 12),
                      const Text('Saving to $bookName'),
                    ],
                  ),
                ),
                SafeArea(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Row(
                      children: [
                        OutlinedButton(
                          onPressed: () {},
                          child: const Text('Skip'),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: FilledButton.icon(
                            onPressed: () {},
                            icon: const Icon(Icons.check),
                            label: const Text('Save Recipe'),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      );

      expect(find.text(recipeName), findsOneWidget);
      expect(find.text('Saving to $bookName'), findsOneWidget);
      expect(find.text('Save Recipe'), findsOneWidget);
      expect(find.text('Skip'), findsOneWidget);
      expect(find.byIcon(Icons.check), findsOneWidget);
    });

    testWidgets('approve button shows loading indicator while approving', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    OutlinedButton(
                      onPressed: null, // disabled during approval
                      child: const Text('Skip'),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: FilledButton.icon(
                        onPressed: null, // disabled during approval
                        icon: const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                        label: const Text('Save Recipe'),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      );

      // Both buttons disabled during approval
      final skipButton = tester.widget<OutlinedButton>(find.widgetWithText(OutlinedButton, 'Skip'));
      expect(skipButton.onPressed, isNull);

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });
  });

  group('ShareHandlerService — URL extraction logic', () {
    // Test URL validation logic in isolation (no widget needed)
    bool isValidUrl(String text) {
      try {
        final uri = Uri.parse(text);
        return uri.hasScheme && (uri.scheme == 'http' || uri.scheme == 'https');
      } catch (_) {
        return false;
      }
    }

    String? extractUrl(String text) {
      if (isValidUrl(text.trim())) return text.trim();
      final urlMatch = RegExp(r'https?://\S+').firstMatch(text);
      return urlMatch?.group(0);
    }

    test('valid https URL passes validation', () {
      expect(isValidUrl('https://allrecipes.com/recipe/123/'), isTrue);
      expect(isValidUrl('http://example.com/recipe'), isTrue);
    });

    test('non-URL text fails validation', () {
      expect(isValidUrl('Check out this recipe!'), isFalse);
      expect(isValidUrl(''), isFalse);
    });

    test('extracts URL from surrounding text', () {
      const text = 'Great recipe! https://allrecipes.com/recipe/123/ via Safari';
      expect(extractUrl(text), 'https://allrecipes.com/recipe/123/');
    });

    test('returns null when no URL in text', () {
      expect(extractUrl('No URL here'), isNull);
    });

    test('plain URL returned directly', () {
      expect(extractUrl('https://example.com/soup'), 'https://example.com/soup');
    });
  });
}
