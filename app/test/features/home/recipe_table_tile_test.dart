import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/home/widgets/recipe_table_tile.dart';

void main() {
  Future<void> pumpTile(
    WidgetTester tester, {
    required Map<String, dynamic> item,
    VoidCallback? onTap,
    VoidCallback? onLongPress,
    bool selected = false,
    Widget? trailing,
  }) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: RecipeTableTile(
          item: item,
          onTap: onTap ?? () {},
          onLongPress: onLongPress,
          selected: selected,
          trailing: trailing,
        ),
      ),
    ));
  }

  testWidgets('renders title and books pill for a recipe with a book',
      (tester) async {
    await pumpTile(tester, item: {
      'id': 'r1',
      'name': 'Pasta Carbonara',
      'recipe_book_name': 'Trying Out',
    });

    expect(find.text('Pasta Carbonara'), findsOneWidget);
    expect(find.text('Trying Out'), findsOneWidget);
  });

  testWidgets('omits books pill when book name is missing', (tester) async {
    await pumpTile(tester, item: {
      'id': 'r2',
      'name': 'Untitled Stew',
    });

    expect(find.text('Untitled Stew'), findsOneWidget);
    expect(find.text('Trying Out'), findsNothing);
  });

  testWidgets('renders chevron when no trailing widget supplied',
      (tester) async {
    await pumpTile(tester, item: {'id': 'r3', 'name': 'X'});
    expect(find.byIcon(Icons.chevron_right), findsOneWidget);
  });

  testWidgets('renders trailing widget in place of chevron', (tester) async {
    await pumpTile(
      tester,
      item: {'id': 'r4', 'name': 'X'},
      trailing: const Text('3 days ago'),
    );
    expect(find.text('3 days ago'), findsOneWidget);
    expect(find.byIcon(Icons.chevron_right), findsNothing);
  });

  testWidgets('shows check_circle when selected', (tester) async {
    await pumpTile(
      tester,
      item: {'id': 'r5', 'name': 'X'},
      selected: true,
    );
    expect(find.byIcon(Icons.check_circle), findsOneWidget);
  });

  testWidgets('tap fires onTap', (tester) async {
    var taps = 0;
    await pumpTile(
      tester,
      item: {'id': 'r6', 'name': 'X'},
      onTap: () => taps++,
    );
    await tester.tap(find.byKey(const ValueKey('recipe_table_tile_r6')));
    await tester.pump();
    expect(taps, 1);
  });

  testWidgets('long-press fires onLongPress', (tester) async {
    var longs = 0;
    await pumpTile(
      tester,
      item: {'id': 'r7', 'name': 'X'},
      onLongPress: () => longs++,
    );
    await tester.longPress(find.byKey(const ValueKey('recipe_table_tile_r7')));
    await tester.pump();
    expect(longs, 1);
  });

  testWidgets('renders meal placeholder icon when meal has no images',
      (tester) async {
    await pumpTile(tester, item: {
      'id': 'm1',
      'name': 'Sunday Brunch',
      'kind': 'meal',
      'component_image_urls': <String>[],
    });
    expect(find.byIcon(Icons.layers_outlined), findsOneWidget);
    expect(find.text('Sunday Brunch'), findsOneWidget);
  });

  testWidgets('renders recipe placeholder icon when no image_url',
      (tester) async {
    await pumpTile(tester, item: {'id': 'r8', 'name': 'X'});
    expect(find.byIcon(Icons.restaurant), findsOneWidget);
  });
}
