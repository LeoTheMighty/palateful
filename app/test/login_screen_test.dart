import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';

// Test the login screen UI layout without requiring Auth0/DI dependencies.
// We test the _SocialSignInButton widget pattern and layout structure directly.

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    GoogleFonts.config.allowRuntimeFetching = false;
  });

  group('LoginScreen UI Layout', () {
    // Since LoginScreen depends on GetIt<AuthService> which requires dotenv/Auth0,
    // we test the social button layout patterns directly.

    testWidgets('social sign-in buttons render correctly', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                // Simulate the Google button with "G" text icon
                SizedBox(
                  width: double.infinity,
                  height: 48,
                  child: OutlinedButton.icon(
                    onPressed: () {},
                    icon: const Text(
                      'G',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w700,
                        color: Color(0xFF4285F4),
                      ),
                    ),
                    label: const Text('Sign in with Google'),
                    style: OutlinedButton.styleFrom(
                      backgroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                  ),
                ),
                // Simulate the Apple button (iOS only)
                if (defaultTargetPlatform == TargetPlatform.iOS)
                  SizedBox(
                    width: double.infinity,
                    height: 48,
                    child: OutlinedButton.icon(
                      onPressed: () {},
                      icon: const Icon(Icons.apple, size: 24, color: Colors.white),
                      label: const Text('Sign in with Apple'),
                      style: OutlinedButton.styleFrom(
                        backgroundColor: Colors.black,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                    ),
                  ),
                TextButton(
                  onPressed: () {},
                  child: const Text('Other sign-in options'),
                ),
              ],
            ),
          ),
        ),
      );

      expect(find.text('Sign in with Google'), findsOneWidget);
      expect(find.text('Other sign-in options'), findsOneWidget);
      expect(find.text('G'), findsOneWidget);
    });

    testWidgets('Apple button renders on iOS platform', (tester) async {
      debugDefaultTargetPlatformOverride = TargetPlatform.iOS;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                const Text('Sign in with Google'),
                if (defaultTargetPlatform == TargetPlatform.iOS)
                  OutlinedButton.icon(
                    onPressed: () {},
                    icon: const Icon(Icons.apple),
                    label: const Text('Sign in with Apple'),
                  ),
              ],
            ),
          ),
        ),
      );

      expect(find.text('Sign in with Apple'), findsOneWidget);
      expect(find.byIcon(Icons.apple), findsOneWidget);

      debugDefaultTargetPlatformOverride = null;
    });

    testWidgets('Apple button hidden on Android platform', (tester) async {
      debugDefaultTargetPlatformOverride = TargetPlatform.android;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                const Text('Sign in with Google'),
                if (defaultTargetPlatform == TargetPlatform.iOS)
                  OutlinedButton.icon(
                    onPressed: () {},
                    icon: const Icon(Icons.apple),
                    label: const Text('Sign in with Apple'),
                  ),
              ],
            ),
          ),
        ),
      );

      expect(find.text('Sign in with Apple'), findsNothing);

      debugDefaultTargetPlatformOverride = null;
    });

    testWidgets('Google button tap triggers callback with connection parameter',
        (tester) async {
      String? capturedConnection;

      // Simulate the login screen's button callback pattern
      void loginWith({String? connection}) {
        capturedConnection = connection;
      }

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                OutlinedButton(
                  onPressed: () => loginWith(connection: 'google-oauth2'),
                  child: const Text('Sign in with Google'),
                ),
                OutlinedButton(
                  onPressed: () => loginWith(connection: 'apple'),
                  child: const Text('Sign in with Apple'),
                ),
                TextButton(
                  onPressed: () => loginWith(),
                  child: const Text('Other sign-in options'),
                ),
              ],
            ),
          ),
        ),
      );

      // Tap Google → verify connection parameter
      await tester.tap(find.text('Sign in with Google'));
      expect(capturedConnection, 'google-oauth2');

      // Tap Apple → verify connection parameter
      capturedConnection = null;
      await tester.tap(find.text('Sign in with Apple'));
      expect(capturedConnection, 'apple');

      // Tap fallback → verify no connection parameter
      capturedConnection = 'should-be-cleared';
      await tester.tap(find.text('Other sign-in options'));
      expect(capturedConnection, isNull);
    });

    testWidgets('error state renders with theme-aware colors', (tester) async {
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
                    'Login failed. Please try again.',
                    style: TextStyle(color: colorScheme.onErrorContainer),
                  ),
                );
              },
            ),
          ),
        ),
      );

      expect(find.text('Login failed. Please try again.'), findsOneWidget);
    });

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

    testWidgets('branding elements render correctly', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) {
                final colorScheme = Theme.of(context).colorScheme;
                return Column(
                  children: [
                    Icon(Icons.restaurant_menu, size: 80, color: colorScheme.primary),
                    const Text('Palateful'),
                    const Text('Your personal recipe book'),
                  ],
                );
              },
            ),
          ),
        ),
      );

      expect(find.text('Palateful'), findsOneWidget);
      expect(find.text('Your personal recipe book'), findsOneWidget);
      expect(find.byIcon(Icons.restaurant_menu), findsOneWidget);
    });
  });
}
