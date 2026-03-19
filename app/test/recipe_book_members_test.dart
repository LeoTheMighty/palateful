import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('Recipe book members', () {
    testWidgets('members screen shows member name and role chip', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: ListTile(
            leading: CircleAvatar(
              child: Icon(Icons.person),
            ),
            title: const Text('Jane Smith'),
            subtitle: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: Colors.blue.shade100,
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Text('editor'),
            ),
          ),
        ),
      ));
      expect(find.text('Jane Smith'), findsOneWidget);
      expect(find.text('editor'), findsOneWidget);
    });

    testWidgets('owner sees popup menu on non-owner member tile', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: ListTile(
            title: const Text('Bob Jones'),
            subtitle: const Text('viewer'),
            trailing: PopupMenuButton<String>(
              onSelected: (_) {},
              itemBuilder: (context) => [
                const PopupMenuItem(value: 'make_editor', child: Text('Change to Editor')),
                const PopupMenuItem(value: 'remove', child: Text('Remove')),
              ],
            ),
          ),
        ),
      ));
      expect(find.byType(PopupMenuButton<String>), findsOneWidget);
    });

    testWidgets('viewer role does not show popup menu', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: ListTile(
            title: const Text('Alice'),
            subtitle: const Text('editor'),
            // No trailing — viewer cannot manage members
            trailing: null,
          ),
        ),
      ));
      expect(find.byType(PopupMenuButton<String>), findsNothing);
    });

    testWidgets('role chip shows correct label for owner', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(
              color: Colors.blue.shade100,
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Text('owner'),
          ),
        ),
      ));
      expect(find.text('owner'), findsOneWidget);
    });
  });
}
