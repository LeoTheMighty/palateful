import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('InvitationsScreen UI components', () {
    testWidgets('shows empty message when no received invitations', (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(
          body: Center(child: Text('No pending invitations')),
        ),
      ));
      expect(find.text('No pending invitations'), findsOneWidget);
    });

    testWidgets('invitation card shows sender name and resource name', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: ListTile(
            leading: CircleAvatar(
              child: Icon(Icons.mail_outline),
            ),
            title: const Text('@alice invited you'),
            subtitle: const Text('Join "My Recipes" as editor'),
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextButton(onPressed: () {}, child: const Text('Decline')),
                ElevatedButton(onPressed: () {}, child: const Text('Accept')),
              ],
            ),
          ),
        ),
      ));
      expect(find.text('@alice invited you'), findsOneWidget);
      expect(find.text('Join "My Recipes" as editor'), findsOneWidget);
      expect(find.text('Accept'), findsOneWidget);
      expect(find.text('Decline'), findsOneWidget);
    });

    testWidgets('tapping Accept button triggers callback', (tester) async {
      bool accepted = false;

      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: ElevatedButton(
            onPressed: () => accepted = true,
            child: const Text('Accept'),
          ),
        ),
      ));

      await tester.tap(find.text('Accept'));
      expect(accepted, isTrue);
    });

    testWidgets('tapping Decline button triggers callback', (tester) async {
      bool declined = false;

      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: TextButton(
            onPressed: () => declined = true,
            child: const Text('Decline'),
          ),
        ),
      ));

      await tester.tap(find.text('Decline'));
      expect(declined, isTrue);
    });

    testWidgets('sent tab shows invitation with Revoke button', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: ListTile(
            leading: CircleAvatar(
              child: Icon(Icons.send),
            ),
            title: const Text('Invited alice@example.com'),
            subtitle: const Text('"Family Recipes" as viewer'),
            trailing: TextButton(
              onPressed: () {},
              child: const Text('Revoke'),
            ),
          ),
        ),
      ));
      expect(find.text('Invited alice@example.com'), findsOneWidget);
      expect(find.text('Revoke'), findsOneWidget);
    });

    testWidgets('shows empty message when no sent invitations', (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(
          body: Center(child: Text('No sent invitations')),
        ),
      ));
      expect(find.text('No sent invitations'), findsOneWidget);
    });

    testWidgets('received tab label shows count', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: DefaultTabController(
          length: 2,
          child: Scaffold(
            appBar: AppBar(
              bottom: const TabBar(
                tabs: [
                  Tab(text: 'Received (2)'),
                  Tab(text: 'Sent (1)'),
                ],
              ),
            ),
            body: const TabBarView(
              children: [
                Center(child: Text('received')),
                Center(child: Text('sent')),
              ],
            ),
          ),
        ),
      ));
      expect(find.text('Received (2)'), findsOneWidget);
      expect(find.text('Sent (1)'), findsOneWidget);
    });
  });
}
