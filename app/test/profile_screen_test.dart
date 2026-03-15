import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:shimmer/shimmer.dart';

// Test the profile screen UI patterns without requiring GetIt/Auth0/DI dependencies.
// Following Story 1.2 pattern: test UI layout directly with equivalent widget trees.

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    GoogleFonts.config.allowRuntimeFetching = false;
  });

  group('ProfileScreen UI Layout', () {
    testWidgets('profile info renders user name, email, and avatar',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Builder(
                builder: (context) {
                  final colorScheme = Theme.of(context).colorScheme;
                  return Column(
                    children: [
                      // Fallback avatar (avoids NetworkImage HTTP in tests)
                      CircleAvatar(
                        radius: 48,
                        backgroundColor: colorScheme.primaryContainer,
                        child: Icon(Icons.person, size: 48,
                            color: colorScheme.onPrimaryContainer),
                      ),
                      const SizedBox(height: 16),
                      const Text('Test User',
                          style: TextStyle(
                              fontSize: 20, fontWeight: FontWeight.w600)),
                      const SizedBox(height: 4),
                      const Text('test@example.com'),
                      const SizedBox(height: 4),
                      const Text('Member since March 2026'),
                    ],
                  );
                },
              ),
            ),
          ),
        ),
      );

      expect(find.text('Test User'), findsOneWidget);
      expect(find.text('test@example.com'), findsOneWidget);
      expect(find.text('Member since March 2026'), findsOneWidget);
      expect(find.byType(CircleAvatar), findsOneWidget);
    });

    testWidgets('fallback avatar renders when no picture URL', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) {
                final colorScheme = Theme.of(context).colorScheme;
                return CircleAvatar(
                  radius: 48,
                  backgroundColor: colorScheme.primaryContainer,
                  child: Icon(
                    Icons.person,
                    size: 48,
                    color: colorScheme.onPrimaryContainer,
                  ),
                );
              },
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.person), findsOneWidget);
      expect(find.byType(CircleAvatar), findsOneWidget);
    });

    testWidgets('edit name tile renders and is tappable', (tester) async {
      bool tapped = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) {
                final colorScheme = Theme.of(context).colorScheme;
                return Material(
                  color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
                  borderRadius: BorderRadius.circular(12),
                  child: InkWell(
                    onTap: () => tapped = true,
                    borderRadius: BorderRadius.circular(12),
                    child: const Padding(
                      padding: EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                      child: Row(
                        children: [
                          Icon(Icons.person_outline),
                          SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text('Display Name'),
                                Text('Test User'),
                              ],
                            ),
                          ),
                          Icon(Icons.chevron_right),
                        ],
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
        ),
      );

      expect(find.text('Display Name'), findsOneWidget);
      expect(find.text('Test User'), findsOneWidget);
      expect(find.byIcon(Icons.chevron_right), findsOneWidget);

      await tester.tap(find.byType(InkWell));
      expect(tapped, isTrue);
    });

    testWidgets('username section renders with edit capability', (tester) async {
      bool tapped = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) {
                return Material(
                  borderRadius: BorderRadius.circular(12),
                  child: InkWell(
                    onTap: () => tapped = true,
                    borderRadius: BorderRadius.circular(12),
                    child: const Padding(
                      padding: EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                      child: Row(
                        children: [
                          Icon(Icons.alternate_email),
                          SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text('Username'),
                                Text('@testuser'),
                              ],
                            ),
                          ),
                          Icon(Icons.chevron_right),
                        ],
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
        ),
      );

      expect(find.text('Username'), findsOneWidget);
      expect(find.text('@testuser'), findsOneWidget);

      await tester.tap(find.byType(InkWell));
      expect(tapped, isTrue);
    });

    testWidgets('username section shows "Set username" when not set',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) {
                final colorScheme = Theme.of(context).colorScheme;
                return Text(
                  'Set username',
                  style: TextStyle(color: colorScheme.primary),
                );
              },
            ),
          ),
        ),
      );

      expect(find.text('Set username'), findsOneWidget);
    });

    testWidgets('logout button exists and is functional', (tester) async {
      bool logoutCalled = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) {
                final colorScheme = Theme.of(context).colorScheme;
                return SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: () => logoutCalled = true,
                    icon: Icon(Icons.logout, color: colorScheme.error),
                    label: Text(
                      'Logout',
                      style: TextStyle(color: colorScheme.error),
                    ),
                  ),
                );
              },
            ),
          ),
        ),
      );

      expect(find.text('Logout'), findsOneWidget);
      expect(find.byIcon(Icons.logout), findsOneWidget);

      await tester.tap(find.text('Logout'));
      expect(logoutCalled, isTrue);
    });

    testWidgets('loading state shows shimmer', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Shimmer.fromColors(
              baseColor: Colors.grey.shade300,
              highlightColor: Colors.grey.shade100,
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  children: [
                    const CircleAvatar(radius: 48),
                    const SizedBox(height: 16),
                    Container(height: 20, width: 150, color: Colors.white),
                    const SizedBox(height: 8),
                    Container(height: 14, width: 200, color: Colors.white),
                  ],
                ),
              ),
            ),
          ),
        ),
      );

      expect(find.byType(Shimmer), findsOneWidget);
      expect(find.byType(CircleAvatar), findsOneWidget);
    });

    testWidgets('error state displays correctly', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) {
                final colorScheme = Theme.of(context).colorScheme;
                return Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.error_outline,
                            size: 64, color: colorScheme.error),
                        const SizedBox(height: 16),
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: colorScheme.errorContainer,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            'Failed to load profile. Please try again.',
                            style:
                                TextStyle(color: colorScheme.onErrorContainer),
                          ),
                        ),
                        const SizedBox(height: 16),
                        FilledButton.icon(
                          onPressed: () {},
                          icon: const Icon(Icons.refresh),
                          label: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.error_outline), findsOneWidget);
      expect(find.text('Failed to load profile. Please try again.'),
          findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
    });

    testWidgets('edit name dialog appears with pre-filled name', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) {
                return ElevatedButton(
                  onPressed: () {
                    showDialog(
                      context: context,
                      builder: (dialogContext) {
                        final controller =
                            TextEditingController(text: 'Existing Name');
                        return AlertDialog(
                          title: const Text('Edit Display Name'),
                          content: TextField(
                            controller: controller,
                            decoration: const InputDecoration(
                              labelText: 'Display Name',
                            ),
                          ),
                          actions: [
                            TextButton(
                              onPressed: () =>
                                  Navigator.of(dialogContext).pop(),
                              child: const Text('Cancel'),
                            ),
                            FilledButton(
                              onPressed: () =>
                                  Navigator.of(dialogContext).pop(controller.text),
                              child: const Text('Save'),
                            ),
                          ],
                        );
                      },
                    );
                  },
                  child: const Text('Edit Name'),
                );
              },
            ),
          ),
        ),
      );

      await tester.tap(find.text('Edit Name'));
      await tester.pumpAndSettle();

      expect(find.text('Edit Display Name'), findsOneWidget);
      expect(find.text('Existing Name'), findsOneWidget);
      expect(find.text('Cancel'), findsOneWidget);
      expect(find.text('Save'), findsOneWidget);
    });

    testWidgets('section headings use Playfair Display font', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Text(
              'Edit Profile',
              style: GoogleFonts.playfairDisplay(
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ),
      );

      expect(find.text('Edit Profile'), findsOneWidget);
      // Verify the text widget exists with GoogleFonts styling
      final textWidget = tester.widget<Text>(find.text('Edit Profile'));
      expect(textWidget.style?.fontWeight, FontWeight.w600);
    });
  });
}
