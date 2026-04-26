import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';

// Mirrors the OnboardingWelcomeScreen UI tree (post-pos-2 reassurance line)
// without invoking the real screen, which depends on GetIt + Auth0.
// Same pattern as `app/test/onboarding_screen_test.dart`.

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    GoogleFonts.config.allowRuntimeFetching = false;
  });

  Widget buildWelcomeTree() {
    return MaterialApp(
      home: Scaffold(
        body: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Builder(
              builder: (context) {
                final textTheme = Theme.of(context).textTheme;
                final colorScheme = Theme.of(context).colorScheme;
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Icon(Icons.restaurant_menu, size: 80),
                    const SizedBox(height: 24),
                    Text(
                      'Welcome to Palateful!',
                      style: textTheme.headlineLarge?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Your recipes, all in one place',
                      style: textTheme.bodyLarge?.copyWith(
                        color: colorScheme.onSurfaceVariant,
                      ),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 6),
                    Text(
                      '100% free, no ads, no premium tier — ever.',
                      style: textTheme.bodySmall?.copyWith(
                        color: colorScheme.onSurfaceVariant,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ],
                );
              },
            ),
          ),
        ),
      ),
    );
  }

  testWidgets(
    'reassurance line renders under the subtitle',
    (tester) async {
      await tester.pumpWidget(buildWelcomeTree());
      expect(find.text('Welcome to Palateful!'), findsOneWidget);
      expect(find.text('Your recipes, all in one place'), findsOneWidget);
      expect(
        find.text('100% free, no ads, no premium tier — ever.'),
        findsOneWidget,
      );
    },
  );

  testWidgets('reassurance line fits at narrow 360px width without overflow',
      (tester) async {
    tester.view.physicalSize = const Size(360, 640);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(buildWelcomeTree());
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });
}
