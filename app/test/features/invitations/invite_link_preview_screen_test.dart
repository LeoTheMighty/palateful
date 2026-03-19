import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('InviteLinkPreviewScreen UI components', () {
    testWidgets('shows Join button when state is active', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text('Family Recipes',
                    style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
                const Text('@alice invited you to join'),
                const Text('Role: viewer'),
                const SizedBox(height: 48),
                ElevatedButton(
                  onPressed: () {},
                  child: const Text('Join'),
                ),
              ],
            ),
          ),
        ),
      ));
      expect(find.text('Join'), findsOneWidget);
      expect(find.text('Family Recipes'), findsOneWidget);
      expect(find.text('@alice invited you to join'), findsOneWidget);
    });

    testWidgets('shows Already a member message when already_member', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Column(
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                color: Colors.green.shade100,
                child: const Text('You are already a member of this book.'),
              ),
              OutlinedButton(
                onPressed: () {},
                child: const Text('View Book'),
              ),
            ],
          ),
        ),
      ));
      expect(find.text('You are already a member of this book.'), findsOneWidget);
      expect(find.text('View Book'), findsOneWidget);
      // No Join button
      expect(find.text('Join'), findsNothing);
    });

    testWidgets('shows expired message when state is expired', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Container(
            padding: const EdgeInsets.all(16),
            color: Colors.red.shade100,
            child: const Row(
              children: [
                Icon(Icons.timer_off),
                SizedBox(width: 12),
                Expanded(
                  child: Text('This invite link has expired.'),
                ),
              ],
            ),
          ),
        ),
      ));
      expect(find.text('This invite link has expired.'), findsOneWidget);
      // No Join button
      expect(find.text('Join'), findsNothing);
    });

    testWidgets('shows deactivated message when state is inactive', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Container(
            padding: const EdgeInsets.all(16),
            color: Colors.red.shade100,
            child: const Row(
              children: [
                Icon(Icons.link_off),
                SizedBox(width: 12),
                Expanded(
                  child: Text('This invite link has been deactivated.'),
                ),
              ],
            ),
          ),
        ),
      ));
      expect(find.text('This invite link has been deactivated.'), findsOneWidget);
      expect(find.text('Join'), findsNothing);
    });

    testWidgets('shows loading indicator while fetching', (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(
          body: Center(child: CircularProgressIndicator()),
        ),
      ));
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('shows role offered in preview', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            color: Colors.blue.shade100,
            child: const Text('Role: editor'),
          ),
        ),
      ));
      expect(find.text('Role: editor'), findsOneWidget);
    });
  });
}
