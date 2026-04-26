import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/home/recipe_list_view.dart';
import 'package:palateful/features/home/widgets/recipe_list_view_toggle_button.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  Future<void> pump(WidgetTester tester) async {
    await tester.pumpWidget(const ProviderScope(
      child: MaterialApp(
        home: Scaffold(body: Center(child: RecipeListViewToggleButton())),
      ),
    ));
  }

  testWidgets('shows grid icon and "Switch to table view" tooltip by default',
      (tester) async {
    await pump(tester);
    expect(find.byIcon(Icons.view_module), findsOneWidget);
    expect(find.byTooltip('Switch to table view'), findsOneWidget);
  });

  testWidgets('tap flips icon, tooltip, and persisted value', (tester) async {
    await pump(tester);

    await tester.tap(find.byKey(const ValueKey('recipe_list_view_toggle')));
    await tester.pump();

    expect(find.byIcon(Icons.view_list), findsOneWidget);
    expect(find.byTooltip('Switch to grid view'), findsOneWidget);

    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('recipe_list_view'), 'table');
  });

  testWidgets('respects pre-set persisted value', (tester) async {
    await tester.pumpWidget(ProviderScope(
      overrides: [
        recipeListViewProvider.overrideWith(
          () => RecipeListViewNotifier(RecipeListView.table),
        ),
      ],
      child: const MaterialApp(
        home: Scaffold(body: Center(child: RecipeListViewToggleButton())),
      ),
    ));
    await tester.pump();
    expect(find.byIcon(Icons.view_list), findsOneWidget);
  });
}
