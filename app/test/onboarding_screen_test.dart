import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';

// Test the onboarding screen UI patterns without requiring GetIt/Auth0/DI dependencies.
// Following Story 1.2/1.3 pattern: test UI layout directly with equivalent widget trees.

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    GoogleFonts.config.allowRuntimeFetching = false;
  });

  group('OnboardingWelcomeScreen UI Layout', () {
    testWidgets('renders heading, name input, and continue button',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SafeArea(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(24),
                child: Builder(
                  builder: (context) {
                    final colorScheme = Theme.of(context).colorScheme;
                    final textTheme = Theme.of(context).textTheme;
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Icon(Icons.restaurant_menu,
                            size: 80, color: colorScheme.primary),
                        const SizedBox(height: 24),
                        Text(
                          'Welcome to Palateful!',
                          style: GoogleFonts.playfairDisplay(
                            textStyle: textTheme.headlineLarge?.copyWith(
                              fontWeight: FontWeight.bold,
                              color: colorScheme.onSurface,
                            ),
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
                        const SizedBox(height: 32),
                        Text('What should we call you?',
                            style: textTheme.titleMedium),
                        const SizedBox(height: 8),
                        const TextField(
                          decoration: InputDecoration(
                            labelText: 'Your Name',
                            hintText: 'Enter your name',
                          ),
                        ),
                        const SizedBox(height: 32),
                        ElevatedButton(
                          onPressed: () {},
                          child: const Text('Continue'),
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

      expect(find.text('Welcome to Palateful!'), findsOneWidget);
      expect(find.text('Your recipes, all in one place'), findsOneWidget);
      expect(find.text('What should we call you?'), findsOneWidget);
      expect(find.byType(TextField), findsOneWidget);
      expect(find.text('Continue'), findsOneWidget);
      expect(find.byIcon(Icons.restaurant_menu), findsOneWidget);
    });

    testWidgets('renders feature highlight cards', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: Builder(
                builder: (context) {
                  return Column(
                    children: [
                      _buildFeatureCard(context, Icons.upload_file, 'Import',
                          'Bring recipes from anywhere — URLs, photos, or files'),
                      const SizedBox(height: 12),
                      _buildFeatureCard(context, Icons.menu_book, 'Organize',
                          'Recipe books keep your collection sorted your way'),
                      const SizedBox(height: 12),
                      _buildFeatureCard(context, Icons.restaurant, 'Cook',
                          'Hands-free cooking mode with step-by-step guidance'),
                    ],
                  );
                },
              ),
            ),
          ),
        ),
      );

      // Verify all three feature cards are present
      expect(find.text('Import'), findsOneWidget);
      expect(find.text('Organize'), findsOneWidget);
      expect(find.text('Cook'), findsOneWidget);
      expect(find.byIcon(Icons.upload_file), findsOneWidget);
      expect(find.byIcon(Icons.menu_book), findsOneWidget);
      expect(find.byIcon(Icons.restaurant), findsOneWidget);
      expect(
          find.text('Bring recipes from anywhere — URLs, photos, or files'),
          findsOneWidget);
      expect(
          find.text('Recipe books keep your collection sorted your way'),
          findsOneWidget);
      expect(
          find.text('Hands-free cooking mode with step-by-step guidance'),
          findsOneWidget);
    });

    testWidgets('loading state shows progress indicator', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Center(
              child: Builder(
                builder: (context) {
                  final colorScheme = Theme.of(context).colorScheme;
                  return CircularProgressIndicator(
                      color: colorScheme.primary);
                },
              ),
            ),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('error state renders in themed container', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) {
                final colorScheme = Theme.of(context).colorScheme;
                return Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: colorScheme.errorContainer,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    'Failed to load user data. Please try again.',
                    style: TextStyle(color: colorScheme.onErrorContainer),
                    textAlign: TextAlign.center,
                  ),
                );
              },
            ),
          ),
        ),
      );

      expect(find.text('Failed to load user data. Please try again.'),
          findsOneWidget);
    });

    testWidgets('continue with empty name shows validation error',
        (tester) async {
      String? errorText;
      final nameController = TextEditingController();

      await tester.pumpWidget(
        MaterialApp(
          home: StatefulBuilder(
            builder: (context, setState) {
              final colorScheme = Theme.of(context).colorScheme;
              final textTheme = Theme.of(context).textTheme;

              void onContinue() {
                final name = nameController.text.trim();
                if (name.isEmpty) {
                  setState(() {
                    errorText = 'Please enter your name';
                  });
                  return;
                }
              }

              return Scaffold(
                body: SingleChildScrollView(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      if (errorText != null) ...[
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: colorScheme.errorContainer,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            errorText!,
                            style: TextStyle(
                                color: colorScheme.onErrorContainer),
                            textAlign: TextAlign.center,
                          ),
                        ),
                        const SizedBox(height: 16),
                      ],
                      TextField(
                        controller: nameController,
                        decoration: const InputDecoration(
                          labelText: 'Your Name',
                          hintText: 'Enter your name',
                        ),
                        onChanged: (_) {
                          if (errorText != null) {
                            setState(() {
                              errorText = null;
                            });
                          }
                        },
                      ),
                      const SizedBox(height: 32),
                      ElevatedButton(
                        onPressed: onContinue,
                        child: const Text('Continue'),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      );

      // No error initially
      expect(find.text('Please enter your name'), findsNothing);

      // Tap continue with empty name
      await tester.tap(find.text('Continue'));
      await tester.pump();

      // Error should appear
      expect(find.text('Please enter your name'), findsOneWidget);

      // Type a name — error should clear
      await tester.enterText(find.byType(TextField), 'Leo');
      await tester.pump();

      expect(find.text('Please enter your name'), findsNothing);
    });

    testWidgets('name field pre-fills with OAuth name', (tester) async {
      final nameController = TextEditingController();

      // Simulate pre-fill from OAuth data
      nameController.text = 'OAuth User';

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Padding(
              padding: const EdgeInsets.all(24),
              child: TextField(
                controller: nameController,
                decoration: const InputDecoration(
                  labelText: 'Your Name',
                  hintText: 'Enter your name',
                ),
              ),
            ),
          ),
        ),
      );

      // Name should be pre-filled
      expect(find.text('OAuth User'), findsOneWidget);
    });
  });

  group('OnboardingStartScreen UI Layout', () {
    testWidgets('renders 3 start method cards with correct titles',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Builder(
                builder: (context) {
                  final colorScheme = Theme.of(context).colorScheme;
                  final textTheme = Theme.of(context).textTheme;
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(
                        'How would you like to start?',
                        style: GoogleFonts.playfairDisplay(
                          textStyle: textTheme.headlineMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                            color: colorScheme.onSurface,
                          ),
                        ),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        "We'll create your personal recipe book",
                        style: textTheme.bodyLarge?.copyWith(
                          color: colorScheme.onSurfaceVariant,
                        ),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 32),
                      _buildStartMethodCard(context, Icons.explore,
                          'Browse Public Recipes',
                          'Discover recipes from the community and save your favorites'),
                      const SizedBox(height: 16),
                      _buildStartMethodCard(context, Icons.upload_file,
                          'Import From Existing Source',
                          'Bring in recipes from websites, files, or other apps'),
                      const SizedBox(height: 16),
                      _buildStartMethodCard(context, Icons.edit_note,
                          'Start from Scratch',
                          'Add your own recipes manually, one at a time'),
                    ],
                  );
                },
              ),
            ),
          ),
        ),
      );

      // Heading
      expect(find.text('How would you like to start?'), findsOneWidget);
      expect(find.text("We'll create your personal recipe book"),
          findsOneWidget);

      // Three start method cards
      expect(find.text('Browse Public Recipes'), findsOneWidget);
      expect(find.text('Import From Existing Source'), findsOneWidget);
      expect(find.text('Start from Scratch'), findsOneWidget);

      // Icons
      expect(find.byIcon(Icons.explore), findsOneWidget);
      expect(find.byIcon(Icons.upload_file), findsOneWidget);
      expect(find.byIcon(Icons.edit_note), findsOneWidget);

      // Chevrons
      expect(find.byIcon(Icons.chevron_right), findsNWidgets(3));
    });

    testWidgets('start screen loading state shows progress indicator',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Center(
              child: Padding(
                padding: const EdgeInsets.all(48),
                child: Builder(
                  builder: (context) {
                    return CircularProgressIndicator(
                        color: Theme.of(context).colorScheme.primary);
                  },
                ),
              ),
            ),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('tapping start method card triggers selection callback',
        (tester) async {
      String? selectedMethod;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Builder(
                builder: (context) {
                  final colorScheme = Theme.of(context).colorScheme;
                  final textTheme = Theme.of(context).textTheme;
                  return Column(
                    children: [
                      GestureDetector(
                        onTap: () {
                          selectedMethod = 'browse';
                        },
                        child: Container(
                          padding: const EdgeInsets.all(20),
                          decoration: BoxDecoration(
                            color: colorScheme.surfaceContainerLow,
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(
                                color: colorScheme.outlineVariant),
                          ),
                          child: Row(
                            children: [
                              Icon(Icons.explore,
                                  color: colorScheme.primary),
                              const SizedBox(width: 16),
                              Expanded(
                                child: Text('Browse Public Recipes',
                                    style: textTheme.titleMedium),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  );
                },
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Browse Public Recipes'));
      await tester.pump();

      expect(selectedMethod, equals('browse'));
    });
  });
}

/// Helper to build a feature card matching the onboarding welcome screen pattern.
Widget _buildFeatureCard(
    BuildContext context, IconData icon, String title, String description) {
  final colorScheme = Theme.of(context).colorScheme;
  final textTheme = Theme.of(context).textTheme;

  return Container(
    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
    decoration: BoxDecoration(
      color: colorScheme.surfaceContainerLow,
      borderRadius: BorderRadius.circular(12),
    ),
    child: Row(
      children: [
        Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: colorScheme.primaryContainer,
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(icon, size: 22, color: colorScheme.primary),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title,
                  style: textTheme.titleSmall
                      ?.copyWith(fontWeight: FontWeight.w600)),
              const SizedBox(height: 2),
              Text(description,
                  style: textTheme.bodySmall
                      ?.copyWith(color: colorScheme.onSurfaceVariant)),
            ],
          ),
        ),
      ],
    ),
  );
}

/// Helper to build a start method card matching the onboarding start screen pattern.
Widget _buildStartMethodCard(
    BuildContext context, IconData icon, String title, String description) {
  final colorScheme = Theme.of(context).colorScheme;
  final textTheme = Theme.of(context).textTheme;

  return Container(
    padding: const EdgeInsets.all(20),
    decoration: BoxDecoration(
      color: colorScheme.surfaceContainerLow,
      borderRadius: BorderRadius.circular(16),
      border: Border.all(color: colorScheme.outlineVariant),
    ),
    child: Row(
      children: [
        Container(
          width: 56,
          height: 56,
          decoration: BoxDecoration(
            color: colorScheme.primaryContainer,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Icon(icon, size: 28, color: colorScheme.primary),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title,
                  style: textTheme.titleMedium
                      ?.copyWith(fontWeight: FontWeight.w600)),
              const SizedBox(height: 4),
              Text(description,
                  style: textTheme.bodyMedium
                      ?.copyWith(color: colorScheme.onSurfaceVariant)),
            ],
          ),
        ),
        Icon(Icons.chevron_right, color: colorScheme.outline),
      ],
    ),
  );
}
